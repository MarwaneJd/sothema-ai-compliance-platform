using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class SearchController : ControllerBase
{
    private readonly IAiService _aiService;
    private readonly IAuditLogRepository _auditLogRepository;
    private readonly ICurrentUserService _currentUserService;

    public SearchController(
        IAiService aiService,
        IAuditLogRepository auditLogRepository,
        ICurrentUserService currentUserService)
    {
        _aiService = aiService;
        _auditLogRepository = auditLogRepository;
        _currentUserService = currentUserService;
    }

    /// <summary>
    /// Hybrid RAG search — proxies the query to the Python AI service
    /// which performs vector + BM25 retrieval with RRF fusion.
    /// </summary>
    [HttpPost]
    public async Task<IActionResult> Search(
        [FromBody] SearchRequest request, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
            return BadRequest("Query must not be empty.");

        var result = await _aiService.SearchAsync(
            request.Query, request.TopK, request.IncludeAnswer, cancellationToken);

        try
        {
            var details = JsonSerializer.Serialize(new
            {
                query = request.Query,
                top_k = request.TopK,
                include_answer = request.IncludeAnswer,
                results_count = result.Results.Count,
                has_answer = result.Answer != null,
            });

            await _auditLogRepository.AddAsync(new AuditLog
            {
                UserId = _currentUserService.ObjectId,
                Action = "SearchQuery",
                EntityType = "Search",
                EntityId = request.Query.Length <= 200
                    ? request.Query
                    : request.Query[..200],
                Timestamp = DateTime.UtcNow,
                Details = details,
            }, cancellationToken);
        }
        catch
        {
            // Audit failure must never affect the search response.
        }

        return Ok(result);
    }

    /// <summary>
    /// Deep Analysis — agentic RAG (Phase 3). Proxies to the Python AI service's
    /// LangGraph loop: plan → retrieve → reflect → (refine_query → retrieve → reflect)*
    /// → generate → verify. p95 latency 5–15s; hard 15s wall-clock inside the agent,
    /// 20s HTTP deadline here.
    /// </summary>
    [HttpPost("agentic")]
    public async Task<IActionResult> AgenticSearch(
        [FromBody] AgenticSearchRequest request, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(request.Query))
            return BadRequest("Query must not be empty.");

        var result = await _aiService.AgenticSearchAsync(
            request.Query, request.TopK, request.MaxIterations, cancellationToken);

        try
        {
            var details = JsonSerializer.Serialize(new
            {
                query = request.Query,
                top_k = request.TopK,
                max_iterations = request.MaxIterations,
                iterations = result.Iterations,
                llm_calls = result.LlmCalls,
                elapsed_ms = result.ElapsedMs,
                groundedness_score = result.GroundednessScore,
                low_confidence = result.LowConfidence,
                citations = result.Citations.Count,
                sub_queries = result.SubQueries,
            });

            await _auditLogRepository.AddAsync(new AuditLog
            {
                UserId = _currentUserService.ObjectId,
                Action = "DeepAnalysisQuery",
                EntityType = "Search",
                EntityId = request.Query.Length <= 200
                    ? request.Query
                    : request.Query[..200],
                Timestamp = DateTime.UtcNow,
                Details = details,
            }, cancellationToken);
        }
        catch
        {
            // Audit failure must never affect the search response.
        }

        return Ok(result);
    }

    public record SearchRequest(string Query, int TopK = 10, bool IncludeAnswer = true);
    public record AgenticSearchRequest(string Query, int TopK = 10, int MaxIterations = 2);
}
