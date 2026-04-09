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
    : ICommand<Result<ComplianceResultDto>>;

public class RequestAnalysisCommandValidator : AbstractValidator<RequestAnalysisCommand>
{
    public RequestAnalysisCommandValidator()
    {
        RuleFor(x => x.DocumentId)
            .NotEqual(Guid.Empty).WithMessage("DocumentId must not be empty.");
    }
}

public class RequestAnalysisCommandHandler
    : IRequestHandler<RequestAnalysisCommand, Result<ComplianceResultDto>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly IComplianceAnalysisRepository _analysisRepository;
    private readonly ISharePointService _sharePointService;
    private readonly IAiService _aiService;
    private readonly IMapper _mapper;

    public RequestAnalysisCommandHandler(
        IDocumentRepository documentRepository,
        IComplianceAnalysisRepository analysisRepository,
        ISharePointService sharePointService,
        IAiService aiService,
        IMapper mapper)
    {
        _documentRepository = documentRepository;
        _analysisRepository = analysisRepository;
        _sharePointService = sharePointService;
        _aiService = aiService;
        _mapper = mapper;
    }

    public async Task<Result<ComplianceResultDto>> Handle(
        RequestAnalysisCommand request, CancellationToken cancellationToken)
    {
        var document = await _documentRepository.GetByIdAsync(
            request.DocumentId, cancellationToken);

        if (document is null)
            return Result<ComplianceResultDto>.Failure(
                $"Document {request.DocumentId} not found.");

        var analysis = new ComplianceAnalysis
        {
            Id = Guid.NewGuid(),
            DocumentId = document.Id,
            Score = 0,
            Summary = string.Empty,
            Status = AnalysisStatus.Pending,
            AnalyzedAt = DateTime.UtcNow
        };

        await _analysisRepository.AddAsync(analysis, cancellationToken);

        var content = await _sharePointService.GetDocumentContentAsync(
            document.SiteId, document.DriveId, document.SharePointItemId,
            cancellationToken);

        await _aiService.RequestAnalysisAsync(
            document.Id, content, document.FileType, cancellationToken);

        analysis.Document = document;

        return Result<ComplianceResultDto>.Success(
            _mapper.Map<ComplianceResultDto>(analysis));
    }
}
