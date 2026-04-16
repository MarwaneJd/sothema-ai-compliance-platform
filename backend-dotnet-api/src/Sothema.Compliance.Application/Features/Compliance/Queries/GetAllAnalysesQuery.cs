using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Compliance.Queries;

public record GetAllAnalysesQuery : IRequest<Result<PaginatedList<ComplianceResultDto>>>
{
    public int Page { get; init; } = 1;
    public int PageSize { get; init; } = 10;
    public string? Status { get; init; }
}

public class GetAllAnalysesQueryHandler
    : IRequestHandler<GetAllAnalysesQuery, Result<PaginatedList<ComplianceResultDto>>>
{
    private readonly IComplianceAnalysisRepository _analysisRepository;
    private readonly IMapper _mapper;

    public GetAllAnalysesQueryHandler(
        IComplianceAnalysisRepository analysisRepository,
        IMapper mapper)
    {
        _analysisRepository = analysisRepository;
        _mapper = mapper;
    }

    public async Task<Result<PaginatedList<ComplianceResultDto>>> Handle(
        GetAllAnalysesQuery request, CancellationToken cancellationToken)
    {
        var all = await _analysisRepository.GetAllAsync(cancellationToken);

        // Filter by status if provided
        var filtered = all.AsEnumerable();
        if (!string.IsNullOrEmpty(request.Status))
        {
            filtered = filtered.Where(a => a.Status.ToString() == request.Status);
        }

        var orderedList = filtered
            .OrderByDescending(a => a.AnalyzedAt)
            .ToList();

        var totalCount = orderedList.Count;

        var pagedItems = orderedList
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        var dtos = _mapper.Map<List<ComplianceResultDto>>(pagedItems);

        return Result<PaginatedList<ComplianceResultDto>>.Success(
            new PaginatedList<ComplianceResultDto>(dtos, totalCount, request.Page, request.PageSize));
    }
}
