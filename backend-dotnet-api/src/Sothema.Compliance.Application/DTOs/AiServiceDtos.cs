using System.Text.Json.Serialization;

namespace Sothema.Compliance.Application.DTOs;

/// <summary>Response from POST /api/analyze on the AI service.</summary>
public record AiAnalysisJobDto
{
    [JsonPropertyName("job_id")]
    public Guid JobId { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("message")]
    public string Message { get; init; } = string.Empty;
}

/// <summary>Response from GET /api/analyze/{jobId}/status on the AI service.</summary>
public record AiAnalysisStatusDto
{
    [JsonPropertyName("job_id")]
    public Guid JobId { get; init; }

    [JsonPropertyName("status")]
    public string Status { get; init; } = string.Empty;

    [JsonPropertyName("score")]
    public double? Score { get; init; }

    [JsonPropertyName("summary")]
    public string? Summary { get; init; }

    [JsonPropertyName("details")]
    public object? Details { get; init; }

    [JsonPropertyName("analyzed_at")]
    public DateTime? AnalyzedAt { get; init; }
}

/// <summary>Response from POST /api/search on the AI service.</summary>
public record AiSearchResponseDto
{
    [JsonPropertyName("query")]
    public string Query { get; init; } = string.Empty;

    [JsonPropertyName("results")]
    public List<AiSearchResultDto> Results { get; init; } = new();

    [JsonPropertyName("total_results")]
    public int TotalResults { get; init; }

    /// <summary>RAG-generated answer from the AI service LLM.</summary>
    [JsonPropertyName("answer")]
    public string? Answer { get; set; }
}

/// <summary>Single search result from the AI service.</summary>
public record AiSearchResultDto
{
    [JsonPropertyName("document_id")]
    public Guid DocumentId { get; init; }

    [JsonPropertyName("document_title")]
    public string DocumentTitle { get; init; } = string.Empty;

    [JsonPropertyName("segment_content")]
    public string SegmentContent { get; init; } = string.Empty;

    [JsonPropertyName("chunk_index")]
    public int ChunkIndex { get; init; }

    [JsonPropertyName("relevance_score")]
    public double RelevanceScore { get; init; }

    [JsonPropertyName("vector_store_id")]
    public string VectorStoreId { get; init; } = string.Empty;
}
