using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Graph;
using Microsoft.Graph.Models;
using MediatR;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Features.Documents.Commands;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;
using Sothema.Compliance.Infrastructure.Persistence;

namespace Sothema.Compliance.Infrastructure.Services;

public enum ChangeClassification
{
    Added,
    Modified,
    Deleted,
    Ignored
}

public class SharePointSyncProcessor : ISyncProcessor
{
    private readonly GraphServiceClient _graphClient;
    private readonly IMediator _mediator;
    private readonly ComplianceDbContext _dbContext;
    private readonly IDocumentRepository _documentRepository;
    private readonly ILogger<SharePointSyncProcessor> _logger;
    private readonly SharePointSyncOptions _options;

    public SharePointSyncProcessor(
        AppGraphClient appGraphClient,
        IMediator mediator,
        ComplianceDbContext dbContext,
        IDocumentRepository documentRepository,
        ILogger<SharePointSyncProcessor> logger,
        IOptions<SharePointSyncOptions> options)
    {
        _graphClient = appGraphClient.Client;
        _mediator = mediator;
        _dbContext = dbContext;
        _documentRepository = documentRepository;
        _logger = logger;
        _options = options.Value;
    }

    public async Task ProcessChangesAsync(CancellationToken cancellationToken = default)
    {
        var state = await GetOrCreateSyncStateAsync(cancellationToken);

        if (string.IsNullOrEmpty(state.DeltaToken))
        {
            _logger.LogInformation(
                "SharePointSyncProcessor: no delta token present — delegating to initial bulk sync.");
            await RunInitialBulkSyncAsync(cancellationToken);
            return;
        }

        _logger.LogInformation(
            "SharePointSyncProcessor: running incremental delta cycle for drive {DriveId}.",
            state.DriveId);

        var (items, nextDeltaLink) = await FetchDeltaAsync(state.DeltaToken, cancellationToken);

        await DispatchChangesAsync(items, cancellationToken);

        state.DeltaToken = nextDeltaLink ?? state.DeltaToken;
        state.LastSyncAt = DateTime.UtcNow;
        await _dbContext.SaveChangesAsync(cancellationToken);

        _logger.LogInformation(
            "SharePointSyncProcessor: delta cycle processed {Count} items.", items.Count);
    }

    public async Task RunInitialBulkSyncAsync(CancellationToken cancellationToken = default)
    {
        var state = await GetOrCreateSyncStateAsync(cancellationToken);

        _logger.LogInformation(
            "SharePointSyncProcessor: starting initial bulk sync for drive {DriveId}.",
            state.DriveId);

        var (items, nextDeltaLink) = await FetchDeltaAsync(deltaLink: null, cancellationToken);

        var batchSize = Math.Max(1, _options.BatchSize);
        var delayMs = Math.Max(0, _options.BatchDelayMilliseconds);
        var processed = 0;

        for (var offset = 0; offset < items.Count; offset += batchSize)
        {
            var batch = items.Skip(offset).Take(batchSize).ToList();
            await DispatchChangesAsync(batch, cancellationToken);
            processed += batch.Count;

            if (offset + batchSize < items.Count && delayMs > 0)
            {
                await Task.Delay(delayMs, cancellationToken);
            }
        }

        state.DeltaToken = nextDeltaLink ?? state.DeltaToken;
        state.LastSyncAt = DateTime.UtcNow;
        await _dbContext.SaveChangesAsync(cancellationToken);

        _logger.LogInformation(
            "SharePointSyncProcessor: initial bulk sync dispatched {Processed} items.",
            processed);
    }

    private async Task<SharePointSyncState> GetOrCreateSyncStateAsync(
        CancellationToken cancellationToken)
    {
        var state = await _dbContext.SharePointSyncStates
            .FirstOrDefaultAsync(
                s => s.SiteId == _options.SiteId && s.DriveId == _options.DriveId,
                cancellationToken);

        if (state is not null) return state;

        state = new SharePointSyncState
        {
            SiteId = _options.SiteId,
            DriveId = _options.DriveId,
            DeltaToken = string.Empty,
            LastSyncAt = DateTime.UtcNow
        };

        _dbContext.SharePointSyncStates.Add(state);

        try
        {
            await _dbContext.SaveChangesAsync(cancellationToken);
        }
        catch (DbUpdateException)
        {
            // Race: another service inserted this row first. Detach and refetch.
            _dbContext.Entry(state).State = EntityState.Detached;
            state = await _dbContext.SharePointSyncStates.FirstOrDefaultAsync(
                s => s.SiteId == _options.SiteId && s.DriveId == _options.DriveId,
                cancellationToken)
                ?? throw new InvalidOperationException(
                    "SharePointSyncState row missing after duplicate-insert recovery.");
        }

        return state;
    }

    private async Task<(List<DriveItem> Items, string? NextDeltaLink)> FetchDeltaAsync(
        string? deltaLink, CancellationToken cancellationToken)
    {
        var collected = new List<DriveItem>();
        string? finalDeltaLink = null;

        var builder = _graphClient.Drives[_options.DriveId].Items["root"].Delta;
        var response = string.IsNullOrEmpty(deltaLink)
            ? await builder.GetAsDeltaGetResponseAsync(cancellationToken: cancellationToken)
            : await builder.WithUrl(deltaLink).GetAsDeltaGetResponseAsync(cancellationToken: cancellationToken);

        while (response is not null)
        {
            if (response.Value is not null)
            {
                collected.AddRange(response.Value);
            }

            if (!string.IsNullOrEmpty(response.OdataDeltaLink))
            {
                finalDeltaLink = response.OdataDeltaLink;
                break;
            }

            if (!string.IsNullOrEmpty(response.OdataNextLink))
            {
                response = await builder
                    .WithUrl(response.OdataNextLink)
                    .GetAsDeltaGetResponseAsync(cancellationToken: cancellationToken);
            }
            else
            {
                break;
            }
        }

        return (collected, finalDeltaLink);
    }

    private async Task DispatchChangesAsync(
        IReadOnlyList<DriveItem> items, CancellationToken cancellationToken)
    {
        foreach (var item in items)
        {
            if (string.IsNullOrEmpty(item.Id)) continue;

            var existing = await _documentRepository.GetBySharePointItemIdAsync(
                item.Id, cancellationToken);

            var classification = ClassifyChange(item, existing);

            try
            {
                switch (classification)
                {
                    case ChangeClassification.Added:
                        await _mediator.Send(new IngestDocumentCommand
                        {
                            SiteId = _options.SiteId,
                            DriveId = _options.DriveId,
                            SharePointItemId = item.Id
                        }, cancellationToken);
                        break;

                    case ChangeClassification.Modified when existing is not null:
                        await _mediator.Send(
                            new RemoveDocumentCommand(existing.Id, DeleteDocumentRow: true),
                            cancellationToken);
                        await _mediator.Send(new IngestDocumentCommand
                        {
                            SiteId = _options.SiteId,
                            DriveId = _options.DriveId,
                            SharePointItemId = item.Id
                        }, cancellationToken);
                        break;

                    case ChangeClassification.Deleted when existing is not null:
                        await _mediator.Send(
                            new RemoveDocumentCommand(existing.Id, DeleteDocumentRow: true),
                            cancellationToken);
                        break;

                    case ChangeClassification.Ignored:
                    default:
                        break;
                }
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "SharePointSyncProcessor: failed to dispatch {Classification} for item {ItemId} — continuing with next item.",
                    classification, item.Id);
            }
        }
    }

    public static ChangeClassification ClassifyChange(DriveItem item, Document? existing)
    {
        if (item.Deleted is not null)
        {
            return existing is null ? ChangeClassification.Ignored : ChangeClassification.Deleted;
        }

        if (item.Folder is not null || item.File is null)
        {
            return ChangeClassification.Ignored;
        }

        return existing is null ? ChangeClassification.Added : ChangeClassification.Modified;
    }
}
