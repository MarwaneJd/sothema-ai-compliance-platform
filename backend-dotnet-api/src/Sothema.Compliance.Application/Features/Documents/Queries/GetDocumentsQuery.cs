using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Documents.Queries;

public record GetDocumentsQuery : IRequest<Result<PaginatedList<DocumentDto>>>
{
    public int PageIndex { get; init; } = 1;
    public int PageSize { get; init; } = 20;
}

public class GetDocumentsQueryHandler
    : IRequestHandler<GetDocumentsQuery, Result<PaginatedList<DocumentDto>>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly IMapper _mapper;

    public GetDocumentsQueryHandler(IDocumentRepository documentRepository, IMapper mapper)
    {
        _documentRepository = documentRepository;
        _mapper = mapper;
    }

    public async Task<Result<PaginatedList<DocumentDto>>> Handle(
        GetDocumentsQuery request, CancellationToken cancellationToken)
    {
        var allDocuments = await _documentRepository.GetAllAsync(cancellationToken);
        var totalCount = allDocuments.Count;

        var pagedItems = allDocuments
            .Skip((request.PageIndex - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        var dtos = _mapper.Map<List<DocumentDto>>(pagedItems);

        return Result<PaginatedList<DocumentDto>>.Success(
            new PaginatedList<DocumentDto>(dtos, totalCount, request.PageIndex, request.PageSize));
    }
}
