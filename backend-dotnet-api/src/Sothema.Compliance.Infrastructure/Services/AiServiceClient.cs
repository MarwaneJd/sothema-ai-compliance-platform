using System.Net.Http.Json;
using System.Text.Json;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Infrastructure.Services;

public class AiServiceClient : IAiService
{
    private readonly HttpClient _httpClient;
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower
    };

    public AiServiceClient(HttpClient httpClient)
    {
        _httpClient = httpClient;
    }

    public async Task<AiAnalysisJobDto> RequestAnalysisAsync(
        Guid documentId, byte[] content, string fileType, string title,
        CancellationToken cancellationToken = default)
    {
        var payload = new
        {
            document_id = documentId,
            document_content = Convert.ToBase64String(content),
            file_type = fileType,
            title = title
        };

        var response = await _httpClient.PostAsJsonAsync(
            "api/analyze", payload, cancellationToken);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<AiAnalysisJobDto>(
            cancellationToken: cancellationToken);

        return result ?? throw new InvalidOperationException("AI service returned no response.");
    }

    public async Task<ComplianceResultDto?> GetAnalysisStatusAsync(
        Guid analysisId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.GetAsync(
            $"api/analyze/{analysisId}/status", cancellationToken);

        if (!response.IsSuccessStatusCode)
            return null;

        var status = await response.Content.ReadFromJsonAsync<AiAnalysisStatusDto>(
            cancellationToken: cancellationToken);

        if (status is null) return null;

        return new ComplianceResultDto
        {
            Id = status.JobId,
            Score = status.Score ?? 0,
            Summary = status.Summary ?? string.Empty,
            Details = status.Details is not null
                ? JsonSerializer.Serialize(status.Details)
                : null,
            Status = status.Status,
            AnalyzedAt = status.AnalyzedAt ?? DateTime.UtcNow
        };
    }

    public async Task<AiSearchResponseDto> SearchAsync(
        string query, int topK = 10, bool includeAnswer = true,
        CancellationToken cancellationToken = default)
    {
        var payload = new { query, top_k = topK, include_answer = includeAnswer };

        var response = await _httpClient.PostAsJsonAsync(
            "api/search", payload, cancellationToken);
        response.EnsureSuccessStatusCode();

        var result = await response.Content.ReadFromJsonAsync<AiSearchResponseDto>(
            cancellationToken: cancellationToken);

        return result ?? new AiSearchResponseDto();
    }

    public async Task IngestDocumentAsync(
        Guid documentId, byte[] content, string fileType, string title,
        CancellationToken cancellationToken = default)
    {
        var payload = new
        {
            document_id = documentId,
            content = Convert.ToBase64String(content),
            file_type = fileType,
            title = title
        };

        var response = await _httpClient.PostAsJsonAsync(
            "api/documents/ingest", payload, cancellationToken);
        response.EnsureSuccessStatusCode();
    }

    public async Task RemoveDocumentAsync(
        Guid documentId, CancellationToken cancellationToken = default)
    {
        var response = await _httpClient.DeleteAsync(
            $"api/documents/{documentId}", cancellationToken);

        if (response.StatusCode == System.Net.HttpStatusCode.NotFound)
            return;

        response.EnsureSuccessStatusCode();
    }
}
