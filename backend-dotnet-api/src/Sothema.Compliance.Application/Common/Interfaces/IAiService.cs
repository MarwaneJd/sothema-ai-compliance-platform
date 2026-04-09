using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Application.Common.Interfaces;

public interface IAiService
{
    Task<Guid> RequestAnalysisAsync(
        Guid documentId, byte[] content, string fileType,
        CancellationToken cancellationToken = default);

    Task<ComplianceResultDto?> GetAnalysisStatusAsync(
        Guid analysisId, CancellationToken cancellationToken = default);

    Task<IReadOnlyList<SharePointSearchResultDto>> SearchSimilarDocumentsAsync(
        string query, CancellationToken cancellationToken = default);
}
