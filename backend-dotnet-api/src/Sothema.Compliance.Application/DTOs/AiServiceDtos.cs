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

// ─── Deep Analysis (agentic RAG) — POST /api/agentic-search ───────────────────

/// <summary>Response from POST /api/agentic-search on the AI service (Phase 3).</summary>
public record AiAgenticSearchResponseDto
{
    [JsonPropertyName("query")]
    public string Query { get; init; } = string.Empty;

    [JsonPropertyName("answer")]
    public string Answer { get; init; } = string.Empty;

    [JsonPropertyName("results")]
    public List<AiSearchResultDto> Results { get; init; } = new();

    [JsonPropertyName("total_results")]
    public int TotalResults { get; init; }

    [JsonPropertyName("citations")]
    public List<AiCitationDto> Citations { get; init; } = new();

    [JsonPropertyName("groundedness_score")]
    public double GroundednessScore { get; init; }

    [JsonPropertyName("low_confidence")]
    public bool LowConfidence { get; init; }

    [JsonPropertyName("iterations")]
    public int Iterations { get; init; }

    [JsonPropertyName("sub_queries")]
    public List<string> SubQueries { get; init; } = new();

    [JsonPropertyName("trace")]
    public List<AiStepLogDto> Trace { get; init; } = new();

    [JsonPropertyName("llm_calls")]
    public int LlmCalls { get; init; }

    [JsonPropertyName("elapsed_ms")]
    public int ElapsedMs { get; init; }
}

/// <summary>Inline citation parsed from the agent's answer ([Source N] → chunk).</summary>
public record AiCitationDto
{
    [JsonPropertyName("source_index")]
    public int SourceIndex { get; init; }

    [JsonPropertyName("document_id")]
    public Guid DocumentId { get; init; }

    [JsonPropertyName("document_title")]
    public string DocumentTitle { get; init; } = string.Empty;

    [JsonPropertyName("chunk_index")]
    public int ChunkIndex { get; init; }

    [JsonPropertyName("vector_store_id")]
    public string VectorStoreId { get; init; } = string.Empty;
}

/// <summary>One step of the agent's execution trace — surfaced for debugging / audit.</summary>
public record AiStepLogDto
{
    [JsonPropertyName("step")]
    public string Step { get; init; } = string.Empty;

    [JsonPropertyName("iteration")]
    public int Iteration { get; init; }

    [JsonPropertyName("elapsed_ms")]
    public int ElapsedMs { get; init; }

    [JsonPropertyName("detail")]
    public string Detail { get; init; } = string.Empty;
}
