using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Microsoft.Graph;
using Microsoft.Graph.Models;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Infrastructure.Persistence;

namespace Sothema.Compliance.Infrastructure.Services;

public class SubscriptionRenewalService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<SubscriptionRenewalService> _logger;
    private readonly SharePointSyncOptions _options;

    public SubscriptionRenewalService(
        IServiceScopeFactory scopeFactory,
        ILogger<SubscriptionRenewalService> logger,
        IOptions<SharePointSyncOptions> options)
    {
        _scopeFactory = scopeFactory;
        _logger = logger;
        _options = options.Value;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        if (!_options.Enabled)
        {
            _logger.LogInformation(
                "SubscriptionRenewalService: disabled via configuration — exiting.");
            return;
        }

        if (string.IsNullOrWhiteSpace(_options.WebhookBaseUrl))
        {
            _logger.LogWarning(
                "SubscriptionRenewalService: WebhookBaseUrl is not configured — skipping subscription lifecycle (polling-only mode).");
            return;
        }

        _logger.LogInformation("SubscriptionRenewalService: started.");

        await EnsureSubscriptionAsync(stoppingToken);

        using var timer = new PeriodicTimer(TimeSpan.FromHours(24));

        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                await RenewIfNeededAsync(stoppingToken);
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown.
        }
    }

    private async Task EnsureSubscriptionAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<ComplianceDbContext>();
            var graphClient = scope.ServiceProvider.GetRequiredService<AppGraphClient>().Client;

            var state = await LoadOrCreateStateAsync(dbContext, cancellationToken);

            var now = DateTime.UtcNow;
            if (!string.IsNullOrEmpty(state.SubscriptionId)
                && state.SubscriptionExpiry.HasValue
                && state.SubscriptionExpiry.Value > now.AddHours(_options.RenewalThresholdHours))
            {
                _logger.LogInformation(
                    "SubscriptionRenewalService: existing subscription {SubId} still valid until {Expiry}.",
                    state.SubscriptionId, state.SubscriptionExpiry);
                return;
            }

            await CreateSubscriptionAsync(graphClient, dbContext, state, cancellationToken);
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "SubscriptionRenewalService: failed to ensure subscription — polling path remains active.");
        }
    }

    private async Task RenewIfNeededAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var dbContext = scope.ServiceProvider.GetRequiredService<ComplianceDbContext>();
            var graphClient = scope.ServiceProvider.GetRequiredService<AppGraphClient>().Client;

            var state = await LoadOrCreateStateAsync(dbContext, cancellationToken);

            var now = DateTime.UtcNow;
            var thresholdMet = !state.SubscriptionExpiry.HasValue
                || state.SubscriptionExpiry.Value <= now.AddHours(_options.RenewalThresholdHours);

            if (!thresholdMet) return;

            if (string.IsNullOrEmpty(state.SubscriptionId))
            {
                await CreateSubscriptionAsync(graphClient, dbContext, state, cancellationToken);
                return;
            }

            try
            {
                var newExpiry = now.AddDays(Math.Max(1, _options.SubscriptionLifetimeDays));
                var update = new Subscription { ExpirationDateTime = newExpiry };

                await graphClient.Subscriptions[state.SubscriptionId]
                    .PatchAsync(update, cancellationToken: cancellationToken);

                state.SubscriptionExpiry = newExpiry;
                await dbContext.SaveChangesAsync(cancellationToken);

                _logger.LogInformation(
                    "SubscriptionRenewalService: renewed subscription {SubId} until {Expiry}.",
                    state.SubscriptionId, newExpiry);
            }
            catch (Microsoft.Graph.Models.ODataErrors.ODataError odataEx)
                when (odataEx.ResponseStatusCode == 404)
            {
                _logger.LogWarning(
                    "SubscriptionRenewalService: subscription {SubId} not found on Graph — creating a new one.",
                    state.SubscriptionId);
                state.SubscriptionId = null;
                state.SubscriptionExpiry = null;
                await dbContext.SaveChangesAsync(cancellationToken);
                await CreateSubscriptionAsync(graphClient, dbContext, state, cancellationToken);
            }
        }
        catch (Exception ex)
        {
            _logger.LogWarning(ex,
                "SubscriptionRenewalService: renewal tick failed — polling path remains active.");
        }
    }

    private async Task CreateSubscriptionAsync(
        GraphServiceClient graphClient,
        ComplianceDbContext dbContext,
        SharePointSyncState state,
        CancellationToken cancellationToken)
    {
        var expiry = DateTime.UtcNow.AddDays(Math.Max(1, _options.SubscriptionLifetimeDays));
        var notificationUrl = _options.WebhookBaseUrl.TrimEnd('/') + "/api/webhooks/sharepoint";

        var subscription = new Subscription
        {
            ChangeType = "updated",
            NotificationUrl = notificationUrl,
            Resource = $"/drives/{_options.DriveId}/root",
            ExpirationDateTime = expiry,
            ClientState = _options.WebhookClientState
        };

        var created = await graphClient.Subscriptions.PostAsync(subscription, cancellationToken: cancellationToken);

        if (created is null || string.IsNullOrEmpty(created.Id))
        {
            _logger.LogWarning(
                "SubscriptionRenewalService: subscription creation returned no id.");
            return;
        }

        state.SubscriptionId = created.Id;
        state.SubscriptionExpiry = created.ExpirationDateTime?.UtcDateTime ?? expiry;
        await dbContext.SaveChangesAsync(cancellationToken);

        _logger.LogInformation(
            "SubscriptionRenewalService: created subscription {SubId} (expires {Expiry}).",
            created.Id, state.SubscriptionExpiry);
    }

    private async Task<SharePointSyncState> LoadOrCreateStateAsync(
        ComplianceDbContext dbContext, CancellationToken cancellationToken)
    {
        var state = await dbContext.SharePointSyncStates
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

        dbContext.SharePointSyncStates.Add(state);

        try
        {
            await dbContext.SaveChangesAsync(cancellationToken);
        }
        catch (DbUpdateException)
        {
            // Race: another service inserted this row first. Detach and refetch.
            dbContext.Entry(state).State = EntityState.Detached;
            state = await dbContext.SharePointSyncStates.FirstOrDefaultAsync(
                s => s.SiteId == _options.SiteId && s.DriveId == _options.DriveId,
                cancellationToken)
                ?? throw new InvalidOperationException(
                    "SharePointSyncState row missing after duplicate-insert recovery.");
        }

        return state;
    }
}
