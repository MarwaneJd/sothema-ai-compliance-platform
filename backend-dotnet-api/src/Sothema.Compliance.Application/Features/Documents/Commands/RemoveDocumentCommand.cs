using FluentValidation;
using MediatR;
using Microsoft.Extensions.Logging;
using Sothema.Compliance.Application.Common.Behaviors;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Documents.Commands;

public record RemoveDocumentCommand(Guid DocumentId, bool DeleteDocumentRow)
    : ICommand<Result<bool>>;

public class RemoveDocumentCommandValidator : AbstractValidator<RemoveDocumentCommand>
{
    public RemoveDocumentCommandValidator()
    {
        RuleFor(x => x.DocumentId)
            .NotEqual(Guid.Empty).WithMessage("DocumentId must not be empty.");
    }
}

public class RemoveDocumentCommandHandler
    : IRequestHandler<RemoveDocumentCommand, Result<bool>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly ITextSegmentRepository _textSegmentRepository;
    private readonly IAiService _aiService;
    private readonly ILogger<RemoveDocumentCommandHandler> _logger;

    public RemoveDocumentCommandHandler(
        IDocumentRepository documentRepository,
        ITextSegmentRepository textSegmentRepository,
        IAiService aiService,
        ILogger<RemoveDocumentCommandHandler> logger)
    {
        _documentRepository = documentRepository;
        _textSegmentRepository = textSegmentRepository;
        _aiService = aiService;
        _logger = logger;
    }

    public async Task<Result<bool>> Handle(
        RemoveDocumentCommand request, CancellationToken cancellationToken)
    {
        var document = await _documentRepository.GetByIdAsync(
            request.DocumentId, cancellationToken);

        if (document is null)
        {
            _logger.LogWarning(
                "RemoveDocumentCommand: Document {DocumentId} not found — nothing to remove.",
                request.DocumentId);
            return Result<bool>.Success(false);
        }

        await _aiService.RemoveDocumentAsync(document.Id, cancellationToken);

        var segments = await _textSegmentRepository.GetByDocumentIdAsync(
            document.Id, cancellationToken);

        foreach (var segment in segments)
        {
            await _textSegmentRepository.DeleteAsync(segment, cancellationToken);
        }

        if (request.DeleteDocumentRow)
        {
            await _documentRepository.DeleteAsync(document, cancellationToken);
        }

        _logger.LogInformation(
            "RemoveDocumentCommand: removed {SegmentCount} segments from document {DocumentId} (deleteRow={DeleteRow}).",
            segments.Count, request.DocumentId, request.DeleteDocumentRow);

        return Result<bool>.Success(true);
    }
}
