using AutoMapper;
using FluentValidation;
using MediatR;
using Sothema.Compliance.Application.Common.Behaviors;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Enums;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Compliance.Commands;

public record RequestAnalysisCommand(Guid DocumentId)
    : ICommand<Result<AiAnalysisJobDto>>;

public class RequestAnalysisCommandValidator : AbstractValidator<RequestAnalysisCommand>
{
    public RequestAnalysisCommandValidator()
    {
        RuleFor(x => x.DocumentId)
            .NotEqual(Guid.Empty).WithMessage("DocumentId must not be empty.");
    }
}

public class RequestAnalysisCommandHandler
    : IRequestHandler<RequestAnalysisCommand, Result<AiAnalysisJobDto>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly ISharePointService _sharePointService;
    private readonly IAiService _aiService;

    public RequestAnalysisCommandHandler(
        IDocumentRepository documentRepository,
        ISharePointService sharePointService,
        IAiService aiService)
    {
        _documentRepository = documentRepository;
        _sharePointService = sharePointService;
        _aiService = aiService;
    }

    public async Task<Result<AiAnalysisJobDto>> Handle(
        RequestAnalysisCommand request, CancellationToken cancellationToken)
    {
        var document = await _documentRepository.GetByIdAsync(
            request.DocumentId, cancellationToken);

        if (document is null)
            return Result<AiAnalysisJobDto>.Failure(
                $"Document {request.DocumentId} not found.");

        // Try to get content from SharePoint; use empty content if stub
        var content = await _sharePointService.GetDocumentContentAsync(
            document.SiteId, document.DriveId, document.SharePointItemId,
            cancellationToken);

        var job = await _aiService.RequestAnalysisAsync(
            document.Id, content, document.FileType, document.Title,
            cancellationToken);

        return Result<AiAnalysisJobDto>.Success(job);
    }
}
