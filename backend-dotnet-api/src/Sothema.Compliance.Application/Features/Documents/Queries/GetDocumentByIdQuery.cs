using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Documents.Queries;

public record GetDocumentByIdQuery(Guid Id) : IRequest<Result<DocumentDto>>;

public class GetDocumentByIdQueryHandler
    : IRequestHandler<GetDocumentByIdQuery, Result<DocumentDto>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly IMapper _mapper;

    public GetDocumentByIdQueryHandler(IDocumentRepository documentRepository, IMapper mapper)
    {
        _documentRepository = documentRepository;
        _mapper = mapper;
    }

    public async Task<Result<DocumentDto>> Handle(
        GetDocumentByIdQuery request, CancellationToken cancellationToken)
    {
        var document = await _documentRepository.GetByIdAsync(request.Id, cancellationToken);

        if (document is null)
            return Result<DocumentDto>.Failure($"Document with ID {request.Id} not found.");

        return Result<DocumentDto>.Success(_mapper.Map<DocumentDto>(document));
    }
}
