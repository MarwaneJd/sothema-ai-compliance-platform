using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Application.Common.Interfaces;

public interface IAiService
{
    Task<AiAnalysisJobDto> RequestAnalysisAsync(
        Guid documentId, byte[] content, string fileType, string title,
        CancellationToken cancellationToken = default);

    Task<ComplianceResultDto?> GetAnalysisStatusAsync(
        Guid analysisId, CancellationToken cancellationToken = default);

    Task<AiSearchResponseDto> SearchAsync(
        string query, int topK = 10, bool includeAnswer = true,
        CancellationToken cancellationToken = default);

    Task IngestDocumentAsync(
        Guid documentId, byte[] content, string fileType, string title,
        CancellationToken cancellationToken = default);

    Task RemoveDocumentAsync(
        Guid documentId, CancellationToken cancellationToken = default);
}
