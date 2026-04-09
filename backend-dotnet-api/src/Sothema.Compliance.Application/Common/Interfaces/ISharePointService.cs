using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Application.Common.Interfaces;

public interface ISharePointService
{
    Task<IReadOnlyList<SharePointSearchResultDto>> SearchDocumentsAsync(
        string query, CancellationToken cancellationToken = default);

    Task<byte[]> GetDocumentContentAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default);

    Task<SharePointSearchResultDto?> GetDocumentMetadataAsync(
        string siteId, string driveId, string itemId,
        CancellationToken cancellationToken = default);
}
