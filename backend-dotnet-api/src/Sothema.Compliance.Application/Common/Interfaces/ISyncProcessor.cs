namespace Sothema.Compliance.Application.Common.Interfaces;

public interface ISyncProcessor
{
    Task ProcessChangesAsync(CancellationToken cancellationToken = default);

    Task RunInitialBulkSyncAsync(CancellationToken cancellationToken = default);
}
