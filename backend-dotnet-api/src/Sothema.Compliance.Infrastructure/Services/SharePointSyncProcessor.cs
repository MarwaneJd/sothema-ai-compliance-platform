using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Graph;
using Microsoft.Graph.Models;
using MediatR;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
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
    private readonly ComplianceDbContext _dbContext;
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<SharePointSyncProcessor> _logger;
    private readonly SharePointSyncOptions _options;

    public SharePointSyncProcessor(
        AppGraphClient appGraphClient,
        ComplianceDbContext dbContext,
        IServiceScopeFactory scopeFactory,
        ILogger<SharePointSyncProcessor> logger,
        IOptions<SharePointSyncOptions> options)
    {
        _graphClient = appGraphClient.Client;
        _dbContext = dbContext;
        _scopeFactory = scopeFactory;
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

        // Commit the new delta token in its OWN transaction, independent of item
        // processing. This MUST advance even if some items above failed —
        // otherwise the next cycle re-fetches the same delta and reprocesses the
        // same items forever (the destructive loop this fix removes).
        await PersistDeltaTokenAsync(state.SiteId, state.DriveId, nextDeltaLink, cancellationToken);

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

        await PersistDeltaTokenAsync(state.SiteId, state.DriveId, nextDeltaLink, cancellationToken);

        _logger.LogInformation(
            "SharePointSyncProcessor: initial bulk sync dispatched {Processed} items.",
            processed);
    }

    private async Task<SharePointSyncState> GetOrCreateSyncStateAsync(
        CancellationToken cancellationToken)
    {
        var state = await _dbContext.SharePointSyncStates
            .AsNoTracking()
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
            state = await _dbContext.SharePointSyncStates.AsNoTracking().FirstOrDefaultAsync(
                s => s.SiteId == _options.SiteId && s.DriveId == _options.DriveId,
                cancellationToken)
                ?? throw new InvalidOperationException(
                    "SharePointSyncState row missing after duplicate-insert recovery.");
        }

        return state;
    }

    /// <summary>
    /// Persist the delta token on a fresh DbContext so the write carries only the
    /// token update — never leftover tracked changes from item dispatch. Without
    /// this isolation, a failed item could poison the shared change tracker and
    /// the token save would throw, leaving the token frozen and the same delta
    /// replaying indefinitely.
    /// </summary>
    private async Task PersistDeltaTokenAsync(
        string siteId, string driveId, string? deltaToken, CancellationToken cancellationToken)
    {
        if (string.IsNullOrEmpty(deltaToken))
        {
            _logger.LogWarning(
                "SharePointSyncProcessor: no next delta link returned — token not advanced this cycle.");
            return;
        }

        using var scope = _scopeFactory.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<ComplianceDbContext>();

        var row = await db.SharePointSyncStates.FirstOrDefaultAsync(
            s => s.SiteId == siteId && s.DriveId == driveId, cancellationToken);
        if (row is null)
        {
            _logger.LogWarning(
                "SharePointSyncProcessor: sync-state row vanished before token persist for drive {DriveId}.",
                driveId);
            return;
        }

        row.DeltaToken = deltaToken;
        row.LastSyncAt = DateTime.UtcNow;
        await db.SaveChangesAsync(cancellationToken);
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

            try
            {
                await DispatchItemInScopeAsync(item, cancellationToken);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "SharePointSyncProcessor: failed to dispatch item {ItemId} — continuing with next item.",
                    item.Id);
            }
        }
    }

    /// <summary>
    /// Process one item in its own DI scope (fresh DbContext + mediator). Isolating
    /// each item means a failure on one cannot leave stale deletes tracked in a
    /// shared context — the source of the original concurrency crashes — and the
    /// Remove/Ingest for a Modified item commit independently.
    /// </summary>
    private async Task DispatchItemInScopeAsync(DriveItem item, CancellationToken cancellationToken)
    {
        using var scope = _scopeFactory.CreateScope();
        var docRepo = scope.ServiceProvider.GetRequiredService<IDocumentRepository>();
        var mediator = scope.ServiceProvider.GetRequiredService<IMediator>();

        var existing = await docRepo.GetBySharePointItemIdAsync(item.Id!, cancellationToken);
        var classification = ClassifyChange(item, existing);

        switch (classification)
        {
            case ChangeClassification.Added:
                await IngestAsync(mediator, item.Id!, cancellationToken, afterDelete: false);
                break;

            case ChangeClassification.Modified when existing is not null:
                await RemoveAsync(mediator, existing.Id, cancellationToken);
                // The remove is destructive; the re-ingest MUST complete or the
                // document is left unindexed. Higher retry budget + loud failure.
                await IngestAsync(mediator, item.Id!, cancellationToken, afterDelete: true);
                break;

            case ChangeClassification.Deleted when existing is not null:
                await RemoveAsync(mediator, existing.Id, cancellationToken);
                break;

            default:
                _logger.LogDebug(
                    "SharePointSyncProcessor: item {ItemId} classified {Classification} — no action.",
                    item.Id, classification);
                break;
        }
    }

    private Task RemoveAsync(IMediator mediator, Guid documentId, CancellationToken cancellationToken)
        => RetryOnConcurrencyAsync(
            () => mediator.Send(new RemoveDocumentCommand(documentId, DeleteDocumentRow: true), cancellationToken),
            $"remove {documentId}", cancellationToken);

    private async Task IngestAsync(
        IMediator mediator, string itemId, CancellationToken cancellationToken, bool afterDelete)
    {
        // A re-ingest following a destructive delete gets a larger retry budget —
        // we have already removed the old document, so failing to re-create it is
        // data loss, not a transient miss.
        var maxAttempts = afterDelete ? 5 : 3;

        try
        {
            var result = await RetryOnConcurrencyAsync(
                () => mediator.Send(new IngestDocumentCommand
                {
                    SiteId = _options.SiteId,
                    DriveId = _options.DriveId,
                    SharePointItemId = itemId
                }, cancellationToken),
                $"ingest {itemId}", cancellationToken, maxAttempts);

            if (!result.IsSuccess)
            {
                if (afterDelete)
                    _logger.LogCritical(
                        "SharePointSyncProcessor: re-ingest of {ItemId} returned failure after a delete ({Error}) — document is now UNINDEXED and needs manual re-sync.",
                        itemId, result.Error);
                else
                    _logger.LogWarning(
                        "SharePointSyncProcessor: ingest of {ItemId} returned failure: {Error}",
                        itemId, result.Error);
            }
        }
        catch (Exception ex) when (afterDelete)
        {
            _logger.LogCritical(ex,
                "SharePointSyncProcessor: re-ingest of {ItemId} threw after a delete — document is now UNINDEXED and needs manual re-sync.",
                itemId);
            throw;
        }
    }

    private async Task<T> RetryOnConcurrencyAsync<T>(
        Func<Task<T>> operation, string label, CancellationToken cancellationToken, int maxAttempts = 3)
    {
        for (var attempt = 1; ; attempt++)
        {
            try
            {
                return await operation();
            }
            catch (DbUpdateConcurrencyException ex) when (attempt < maxAttempts)
            {
                _logger.LogWarning(ex,
                    "SharePointSyncProcessor: {Label} hit a concurrency conflict (attempt {Attempt}/{Max}) — retrying.",
                    label, attempt, maxAttempts);
                await Task.Delay(200 * attempt, cancellationToken);
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

        if (existing is null)
        {
            return ChangeClassification.Added;
        }

        // Existing document: only a genuine content change warrants the destructive
        // remove + re-ingest. Delta legitimately re-surfaces unchanged items (a
        // replayed token, a metadata-only touch), so skip them when the content
        // hash matches what we already indexed — this prevents the spurious
        // Modified churn that was wiping the corpus.
        var incomingHash = ContentHashOf(item);
        if (!string.IsNullOrEmpty(incomingHash) &&
            string.Equals(incomingHash, existing.ContentHash, StringComparison.Ordinal))
        {
            return ChangeClassification.Ignored;
        }

        return ChangeClassification.Modified;
    }

    /// <summary>Content identity for change detection: quickXorHash, then cTag, then eTag.</summary>
    internal static string? ContentHashOf(DriveItem item)
        => item.File?.Hashes?.QuickXorHash ?? item.CTag ?? item.ETag;
}
