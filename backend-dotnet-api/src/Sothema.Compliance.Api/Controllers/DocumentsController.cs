using MediatR;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Application.Features.Documents.Commands;
using Sothema.Compliance.Application.Features.Documents.Queries;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class DocumentsController : ControllerBase
{
    private readonly IMediator _mediator;

    public DocumentsController(IMediator mediator)
    {
        _mediator = mediator;
    }

    [HttpGet]
    public async Task<IActionResult> GetDocuments(
        [FromQuery] int page = 1,
        [FromQuery] int pageSize = 20,
        CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(
            new GetDocumentsQuery { Page = page, PageSize = pageSize },
            cancellationToken);

        return result.IsSuccess ? Ok(result.Value) : BadRequest(result.Error);
    }

    [HttpGet("{id:guid}")]
    public async Task<IActionResult> GetDocumentById(
        Guid id, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new GetDocumentByIdQuery(id), cancellationToken);

        if (!result.IsSuccess)
            return NotFound(result.Error);

        return Ok(result.Value);
    }

    [HttpGet("search")]
    public async Task<IActionResult> SearchDocuments(
        [FromQuery] string q, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new SearchDocumentsQuery(q), cancellationToken);

        return result.IsSuccess ? Ok(result.Value) : BadRequest(result.Error);
    }

    [HttpGet("{id:guid}/content")]
    public async Task<IActionResult> GetDocumentContent(
        Guid id, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(new GetDocumentContentQuery(id), cancellationToken);

        if (!result.IsSuccess)
            return NotFound(result.Error);

        return File(result.Value!, "application/octet-stream");
    }

    [HttpPost("ingest")]
    [Authorize(Policy = "RequireAnalyst")]
    public async Task<IActionResult> IngestDocument(
        [FromBody] IngestDocumentCommand command, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(command, cancellationToken);

        if (!result.IsSuccess)
            return BadRequest(result.Error);

        return CreatedAtAction(nameof(GetDocumentById), new { id = result.Value!.Id }, result.Value);
    }

    // Cascades to FAISS + BM25 (via AI service) + TextSegments + Document row.
    // Admin-only because deletion is destructive and irreversible.
    [HttpDelete("{id:guid}")]
    [Authorize(Policy = "RequireAdmin")]
    public async Task<IActionResult> DeleteDocument(
        Guid id, CancellationToken cancellationToken = default)
    {
        var result = await _mediator.Send(
            new RemoveDocumentCommand(id, DeleteDocumentRow: true),
            cancellationToken);

        if (!result.IsSuccess)
            return BadRequest(result.Error);

        // Result.Value is false when the document didn't exist.
        return result.Value ? NoContent() : NotFound();
    }
}
