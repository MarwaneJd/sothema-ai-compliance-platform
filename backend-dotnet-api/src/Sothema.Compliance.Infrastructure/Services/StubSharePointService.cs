using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Infrastructure.Services;

/// <summary>
/// Stub implementation used when SharePoint/Entra ID credentials are not available.
/// Reads document content from a local dev-files cache (populated by DevController.IngestFile).
/// </summary>
public class StubSharePointService : ISharePointService
{
    // Shared cache path — must match DevController.GetDevFilesPath()
    public static string DevFilesPath =>
        Path.Combine(Path.GetTempPath(), "sothema-dev-files");

    public Task<IReadOnlyList<SharePointSearchResultDto>> SearchDocumentsAsync(
        string query, CancellationToken cancellationToken = default)
    {
        IReadOnlyList<SharePointSearchResultDto> results = Array.Empty<SharePointSearchResultDto>();
        return Task.FromResult(results);
    }

    public async Task<byte[]> GetDocumentContentAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default)
    {
        // The itemId for dev uploads is "dev-{guid}" — look for any file with that prefix
        if (!Directory.Exists(DevFilesPath))
            return Array.Empty<byte>();

        var matches = Directory.GetFiles(DevFilesPath, $"{itemId}.*");
        if (matches.Length == 0)
            return Array.Empty<byte>();

        return await File.ReadAllBytesAsync(matches[0], cancellationToken);
    }

    public Task<SharePointSearchResultDto?> GetDocumentMetadataAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default)
    {
        return Task.FromResult<SharePointSearchResultDto?>(null);
    }
}
