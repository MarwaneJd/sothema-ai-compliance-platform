using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Common.Interfaces;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class SearchController : ControllerBase
{
    private readonly IAiService _aiService;

    public SearchController(IAiService aiService)
    {
        _aiService = aiService;
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
            request.Query, request.TopK, cancellationToken);

        return Ok(result);
    }

    public record SearchRequest(string Query, int TopK = 10);
}
