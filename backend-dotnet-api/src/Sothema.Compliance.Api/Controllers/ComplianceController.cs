using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Features.Compliance.Commands;
using Sothema.Compliance.Application.Features.Compliance.Queries;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ComplianceController : ControllerBase
{
    private readonly IMediator _mediator;

    public ComplianceController(IMediator mediator)
    {
        _mediator = mediator;
    }

    /// <summary>List all compliance analyses (paginated, filterable by status).</summary>
    [HttpGet]
    public async Task<IActionResult> GetAnalyses(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 10,
        [FromQuery] string? status = null,
        CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new GetAllAnalysesQuery
        {
            Page = page,
            PageSize = pageSize,
            Status = status
        }, cancellationToken);

        return result.IsSuccess ? Ok(result.Value) : BadRequest(result.Error);
    }

    /// <summary>Get a single compliance analysis by its ID.</summary>
    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetAnalysisById(
        Guid id, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new GetAnalysisByIdQuery(id), cancellationToken);

        return result.IsSuccess ? Ok(result.Value) : NotFound(result.Error);
    }

    /// <summary>Get all analyses for a given document.</summary>
    [HttpGet("document/{documentId:guid}")]
    public async Task<IActionResult> GetAnalysesByDocument(
        Guid documentId, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new GetAnalysisQuery(documentId), cancellationToken);

        return result.IsSuccess ? Ok(result.Value) : NotFound(result.Error);
    }

    /// <summary>Trigger a new compliance analysis for a document.</summary>
    [HttpPost("analyze")]
    [Authorize(Policy = "RequireAnalyst")]
    public async Task<IActionResult> RequestAnalysis(
        [FromBody] RequestAnalysisCommand command, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(command, cancellationToken);

        if (!result.IsSuccess)
            return BadRequest(result.Error);

        return Ok(result.Value);
    }
}
