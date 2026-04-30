using Microsoft.Graph;

namespace Sothema.Compliance.Infrastructure.Services;

/// <summary>
/// Wrapper around a client-credentials (app-only) GraphServiceClient.
/// Used by background services that have no user context — subscription
/// management, delta polling, drive enumeration — where delegated/OBO
/// auth cannot be used.
/// </summary>
public class AppGraphClient
{
    public GraphServiceClient Client { get; }

    public AppGraphClient(GraphServiceClient client)
    {
        Client = client;
    }
}
