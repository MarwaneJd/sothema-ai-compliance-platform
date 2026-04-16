using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Compliance.Queries;

public record GetAnalysisByIdQuery(Guid AnalysisId)
    : IRequest<Result<ComplianceResultDto>>;

public class GetAnalysisByIdQueryHandler
    : IRequestHandler<GetAnalysisByIdQuery, Result<ComplianceResultDto>>
{
    private readonly IComplianceAnalysisRepository _analysisRepository;
    private readonly IMapper _mapper;

    public GetAnalysisByIdQueryHandler(
        IComplianceAnalysisRepository analysisRepository,
        IMapper mapper)
    {
        _analysisRepository = analysisRepository;
        _mapper = mapper;
    }

    public async Task<Result<ComplianceResultDto>> Handle(
        GetAnalysisByIdQuery request, CancellationToken cancellationToken)
    {
        var analysis = await _analysisRepository.GetByIdAsync(
            request.AnalysisId, cancellationToken);

        if (analysis is null)
            return Result<ComplianceResultDto>.Failure(
                $"Analysis {request.AnalysisId} not found.");

        var dto = _mapper.Map<ComplianceResultDto>(analysis);
        return Result<ComplianceResultDto>.Success(dto);
    }
}
