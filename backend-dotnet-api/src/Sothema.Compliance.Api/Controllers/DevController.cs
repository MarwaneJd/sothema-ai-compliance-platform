using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;
using Sothema.Compliance.Infrastructure.Persistence;
using Sothema.Compliance.Infrastructure.Services;

namespace Sothema.Compliance.Api.Controllers;

/// <summary>
/// Development-only controller for seeding test data and ingesting documents
/// without SharePoint credentials.
/// REMOVE THIS CONTROLLER (or the entire file) before production deployment.
/// </summary>
[ApiController]
[Route("api/dev")]
[Authorize]
public class DevController : ControllerBase
{
    private readonly IDocumentRepository _documentRepository;
    private readonly IAiService _aiService;
    private readonly IWebHostEnvironment _env;

    public DevController(
        IDocumentRepository documentRepository,
        IAiService aiService,
        IWebHostEnvironment env)
    {
        _documentRepository = documentRepository;
        _aiService = aiService;
        _env = env;
    }

    /// <summary>
    /// Ingest a document file directly (no SharePoint needed).
    /// Accepts multipart/form-data with a "file" field.
    /// Only available in Development environment.
    /// </summary>
    [HttpPost("ingest")]
    [RequestSizeLimit(50 * 1024 * 1024)] // 50 MB limit
    public async Task<IActionResult> IngestFile(
        IFormFile file, CancellationToken cancellationToken = default)
    {
        if (!_env.IsDevelopment())
            return NotFound(); // Invisible in production

        if (file is null || file.Length == 0)
            return BadRequest("No file provided.");

        var allowedExtensions = new[] { ".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".md" };
        var ext = Path.GetExtension(file.FileName).ToLowerInvariant();
        if (!allowedExtensions.Contains(ext))
            return BadRequest($"Unsupported file type '{ext}'. Allowed: {string.Join(", ", allowedExtensions)}");

        // Read file bytes
        using var ms = new MemoryStream();
        await file.CopyToAsync(ms, cancellationToken);
        var content = ms.ToArray();

        // Persist the file bytes to the dev cache so later re-analysis can read them
        Directory.CreateDirectory(StubSharePointService.DevFilesPath);
        var devItemId = $"dev-{Guid.NewGuid()}";
        var cachePath = Path.Combine(
            StubSharePointService.DevFilesPath, $"{devItemId}{ext}");
        await System.IO.File.WriteAllBytesAsync(cachePath, content, cancellationToken);

        // Create Document record
        var document = new Document
        {
            Id = Guid.NewGuid(),
            SharePointItemId = devItemId,
            Title = Path.GetFileNameWithoutExtension(file.FileName),
            SiteId = "dev-site",
            DriveId = "dev-drive",
            ContentType = file.ContentType ?? "application/octet-stream",
            FileType = ext.TrimStart('.'),
            SharePointUrl = $"file://{file.FileName}",
            UploadedAt = DateTime.UtcNow
        };

        await _documentRepository.AddAsync(document, cancellationToken);

        // Send to AI service for indexing
        var job = await _aiService.RequestAnalysisAsync(
            document.Id, content, document.FileType, document.Title, cancellationToken);

        return Ok(new
        {
            document.Id,
            document.Title,
            document.FileType,
            IngestionJob = new { job.JobId, job.Status },
            Message = "Document ingested and analysis queued. Poll GET /api/compliance/{jobId} for results."
        });
    }

    /// <summary>
    /// Seed a few sample placeholder documents (no real content — just metadata).
    /// Useful for testing the UI listing without running the full AI pipeline.
    /// Only available in Development environment.
    /// </summary>
    [HttpPost("seed")]
    public async Task<IActionResult> SeedSampleDocuments(CancellationToken cancellationToken = default)
    {
        if (!_env.IsDevelopment())
            return NotFound();

        var samples = new[]
        {
            ("ICH Q7 GMP Guide for Active Pharmaceutical Ingredients", "pdf"),
            ("WHO GMP Guidelines for Pharmaceutical Products", "pdf"),
            ("SOP-QC-001 Quality Control Standard Operating Procedure", "docx"),
            ("FDA 21 CFR Part 211 Current Good Manufacturing Practice", "pdf"),
            ("ICH Q10 Pharmaceutical Quality System", "pdf"),
        };

        var created = new List<object>();
        foreach (var (title, fileType) in samples)
        {
            var itemId = $"dev-seed-{Guid.NewGuid()}";
            var existing = await _documentRepository.GetBySharePointItemIdAsync(itemId, cancellationToken);
            if (existing is not null) continue;

            var doc = new Document
            {
                Id = Guid.NewGuid(),
                SharePointItemId = itemId,
                Title = title,
                SiteId = "dev-site",
                DriveId = "dev-drive",
                ContentType = "application/octet-stream",
                FileType = fileType,
                SharePointUrl = $"file://{title.Replace(" ", "_")}.{fileType}",
                UploadedAt = DateTime.UtcNow
            };
            await _documentRepository.AddAsync(doc, cancellationToken);
            created.Add(new { doc.Id, doc.Title });
        }

        return Ok(new
        {
            Message = $"Seeded {created.Count} sample documents.",
            Documents = created
        });
    }
}
