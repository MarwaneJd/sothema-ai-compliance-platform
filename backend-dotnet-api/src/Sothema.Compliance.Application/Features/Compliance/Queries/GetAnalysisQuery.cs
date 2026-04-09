using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Compliance.Queries;

public record GetAnalysisQuery(Guid DocumentId)
    : IRequest<Result<IReadOnlyList<ComplianceResultDto>>>;

public class GetAnalysisQueryHandler
    : IRequestHandler<GetAnalysisQuery, Result<IReadOnlyList<ComplianceResultDto>>>
{
    private readonly IComplianceAnalysisRepository _analysisRepository;
    private readonly IMapper _mapper;

    public GetAnalysisQueryHandler(
        IComplianceAnalysisRepository analysisRepository,
        IMapper mapper)
    {
        _analysisRepository = analysisRepository;
        _mapper = mapper;
    }

    public async Task<Result<IReadOnlyList<ComplianceResultDto>>> Handle(
        GetAnalysisQuery request, CancellationToken cancellationToken)
    {
        var analyses = await _analysisRepository.GetByDocumentIdAsync(
            request.DocumentId, cancellationToken);

        var dtos = _mapper.Map<IReadOnlyList<ComplianceResultDto>>(analyses);

        return Result<IReadOnlyList<ComplianceResultDto>>.Success(dtos);
    }
}
