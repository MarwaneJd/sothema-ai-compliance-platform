using MediatR;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.Documents.Queries;

public record GetDocumentContentQuery(Guid DocumentId) : IRequest<Result<byte[]>>;

public class GetDocumentContentQueryHandler
    : IRequestHandler<GetDocumentContentQuery, Result<byte[]>>
{
    private readonly IDocumentRepository _documentRepository;
    private readonly ISharePointService _sharePointService;

    public GetDocumentContentQueryHandler(
        IDocumentRepository documentRepository,
        ISharePointService sharePointService)
    {
        _documentRepository = documentRepository;
        _sharePointService = sharePointService;
    }

    public async Task<Result<byte[]>> Handle(
        GetDocumentContentQuery request, CancellationToken cancellationToken)
    {
        var document = await _documentRepository.GetByIdAsync(
            request.DocumentId, cancellationToken);

        if (document is null)
            return Result<byte[]>.Failure($"Document {request.DocumentId} not found.");

        var content = await _sharePointService.GetDocumentContentAsync(
            document.SiteId, document.DriveId, document.SharePointItemId,
            cancellationToken);

        return Result<byte[]>.Success(content);
    }
}
