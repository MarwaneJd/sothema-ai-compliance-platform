using Microsoft.AspNetCore.Http;
using Microsoft.Graph;
using Microsoft.Graph.Models;
using Microsoft.Graph.Search.Query;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Infrastructure.Services;

public class SharePointService : ISharePointService
{
    private readonly GraphServiceClient _oboClient;
    private readonly AppGraphClient? _appClient;
    private readonly IHttpContextAccessor _httpContext;

    public SharePointService(
        GraphServiceClient oboClient,
        IHttpContextAccessor httpContext,
        AppGraphClient? appClient = null)
    {
        _oboClient = oboClient;
        _httpContext = httpContext;
        _appClient = appClient;
    }

    /// <summary>
    /// OBO when a user is on the request (preserves SharePoint ACL),
    /// app-only when running headless (background sync, webhook dispatch).
    /// </summary>
    private GraphServiceClient PickClient()
    {
        var hasUser = _httpContext.HttpContext?.User?.Identity?.IsAuthenticated == true;
        if (!hasUser && _appClient is not null) return _appClient.Client;
        return _oboClient;
    }

    public async Task<IReadOnlyList<SharePointSearchResultDto>> SearchDocumentsAsync(
        string query, CancellationToken cancellationToken = default)
    {
        var searchResult = await PickClient().Search.Query.PostAsQueryPostResponseAsync(
            new QueryPostRequestBody
            {
                Requests = new List<SearchRequest>
                {
                    new()
                    {
                        EntityTypes = new List<EntityType?>
                        {
                            EntityType.DriveItem
                        },
                        Query = new SearchQuery
                        {
                            QueryString = query
                        }
                    }
                }
            },
            cancellationToken: cancellationToken);

        var results = new List<SharePointSearchResultDto>();

        var hitsContainers = searchResult?.Value?.FirstOrDefault()?.HitsContainers;
        if (hitsContainers == null) return results;

        foreach (var container in hitsContainers)
        {
            if (container.Hits == null) continue;

            foreach (var hit in container.Hits)
            {
                if (hit.Resource is not DriveItem driveItem) continue;

                results.Add(new SharePointSearchResultDto
                {
                    SharePointItemId = driveItem.Id ?? string.Empty,
                    Title = driveItem.Name ?? string.Empty,
                    ContentType = driveItem.File?.MimeType ?? string.Empty,
                    FileType = Path.GetExtension(driveItem.Name ?? string.Empty).TrimStart('.'),
                    SharePointUrl = driveItem.WebUrl ?? string.Empty,
                    LastModified = driveItem.LastModifiedDateTime?.DateTime
                });
            }
        }

        return results;
    }

    public async Task<byte[]> GetDocumentContentAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default)
    {
        var stream = await PickClient().Drives[driveId]
            .Items[itemId]
            .Content
            .GetAsync(cancellationToken: cancellationToken);

        if (stream == null)
            return Array.Empty<byte>();

        using var memoryStream = new MemoryStream();
        await stream.CopyToAsync(memoryStream, cancellationToken);
        return memoryStream.ToArray();
    }

    public async Task<SharePointSearchResultDto?> GetDocumentMetadataAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default)
    {
        var driveItem = await PickClient().Drives[driveId]
            .Items[itemId]
            .GetAsync(cancellationToken: cancellationToken);

        if (driveItem == null) return null;

        return new SharePointSearchResultDto
        {
            SharePointItemId = driveItem.Id ?? string.Empty,
            Title = driveItem.Name ?? string.Empty,
            SiteId = siteId,
            DriveId = driveId,
            ContentType = driveItem.File?.MimeType ?? string.Empty,
            FileType = Path.GetExtension(driveItem.Name ?? string.Empty).TrimStart('.'),
            SharePointUrl = driveItem.WebUrl ?? string.Empty,
            LastModified = driveItem.LastModifiedDateTime?.DateTime
        };
    }
}
