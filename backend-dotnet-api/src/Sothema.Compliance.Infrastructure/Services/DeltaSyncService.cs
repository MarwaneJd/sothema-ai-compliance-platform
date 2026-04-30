using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Sothema.Compliance.Application.Common.Interfaces;

namespace Sothema.Compliance.Infrastructure.Services;

public class DeltaSyncService : BackgroundService
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly ILogger<DeltaSyncService> _logger;
    private readonly SharePointSyncOptions _options;

    public DeltaSyncService(
        IServiceScopeFactory scopeFactory,
        ILogger<DeltaSyncService> logger,
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
                "DeltaSyncService: disabled via configuration — exiting.");
            return;
        }

        var intervalMinutes = Math.Max(1, _options.PollingIntervalMinutes);
        using var timer = new PeriodicTimer(TimeSpan.FromMinutes(intervalMinutes));

        _logger.LogInformation(
            "DeltaSyncService: started (interval={Interval} min).", intervalMinutes);

        await RunOnceAsync(stoppingToken);

        try
        {
            while (await timer.WaitForNextTickAsync(stoppingToken))
            {
                await RunOnceAsync(stoppingToken);
            }
        }
        catch (OperationCanceledException)
        {
            // Normal shutdown.
        }
    }

    private async Task RunOnceAsync(CancellationToken cancellationToken)
    {
        try
        {
            using var scope = _scopeFactory.CreateScope();
            var processor = scope.ServiceProvider.GetRequiredService<ISyncProcessor>();
            await processor.ProcessChangesAsync(cancellationToken);
        }
        catch (OperationCanceledException)
        {
            throw;
        }
        catch (Exception ex)
        {
            _logger.LogError(ex,
                "DeltaSyncService: iteration failed — will retry on next tick.");
        }
    }
}
