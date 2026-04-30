using AutoMapper;
using FluentValidation;
using MediatR;
using Sothema.Compliance.Application.Common.Behaviors;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Documents.Commands;

public record IngestDocumentCommand : ICommand<Result<DocumentDto>>
{
    public string SiteId { get; init; } = string.Empty;
    public string DriveId { get; init; } = string.Empty;
    public string SharePointItemId { get; init; } = string.Empty;
}

public class IngestDocumentCommandValidator : AbstractValidator<IngestDocumentCommand>
{
    public IngestDocumentCommandValidator()
    {
        RuleFor(x => x.SiteId).NotEmpty().WithMessage("SiteId is required.");
        RuleFor(x => x.DriveId).NotEmpty().WithMessage("DriveId is required.");
        RuleFor(x => x.SharePointItemId).NotEmpty().WithMessage("SharePointItemId is required.");
    }
}

public class IngestDocumentCommandHandler
    : IRequestHandler<IngestDocumentCommand, Result<DocumentDto>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly ISharePointService _sharePointService;
    private readonly IAiService _aiService;
    private readonly IMapper _mapper;

    public IngestDocumentCommandHandler(
        IDocumentRepository documentRepository,
        ISharePointService sharePointService,
        IAiService aiService,
        IMapper mapper)
    {
        _documentRepository = documentRepository;
        _sharePointService = sharePointService;
        _aiService = aiService;
        _mapper = mapper;
    }

    public async Task<Result<DocumentDto>> Handle(
        IngestDocumentCommand request, CancellationToken cancellationToken)
    {
        var existing = await _documentRepository.GetBySharePointItemIdAsync(
            request.SharePointItemId, cancellationToken);

        if (existing is not null)
            return Result<DocumentDto>.Failure(
                $"Document with SharePoint item ID {request.SharePointItemId} already ingested.");

        var metadata = await _sharePointService.GetDocumentMetadataAsync(
            request.SiteId, request.DriveId, request.SharePointItemId, cancellationToken);

        if (metadata is null)
            return Result<DocumentDto>.Failure("Document not found in SharePoint.");

        var document = new Document
        {
            Id = Guid.NewGuid(),
            SharePointItemId = request.SharePointItemId,
            Title = metadata.Title,
            SiteId = request.SiteId,
            DriveId = request.DriveId,
            ContentType = metadata.ContentType,
            FileType = metadata.FileType,
            SharePointUrl = metadata.SharePointUrl,
            UploadedAt = DateTime.UtcNow
        };

        await _documentRepository.AddAsync(document, cancellationToken);

        var content = await _sharePointService.GetDocumentContentAsync(
            request.SiteId, request.DriveId, request.SharePointItemId, cancellationToken);

        await _aiService.IngestDocumentAsync(
            document.Id, content, document.FileType, document.Title, cancellationToken);

        return Result<DocumentDto>.Success(_mapper.Map<DocumentDto>(document));
    }
}
