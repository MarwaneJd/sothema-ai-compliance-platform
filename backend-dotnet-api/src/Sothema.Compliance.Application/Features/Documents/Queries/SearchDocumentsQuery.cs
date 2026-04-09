using FluentValidation;
using MediatR;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Application.Features.Documents.Queries;

public record SearchDocumentsQuery(string Query)
    : IRequest<Result<IReadOnlyList<SharePointSearchResultDto>>>;

public class SearchDocumentsQueryValidator : AbstractValidator<SearchDocumentsQuery>
{
    public SearchDocumentsQueryValidator()
    {
        RuleFor(x => x.Query)
            .NotEmpty().WithMessage("Search query must not be empty.")
            .MaximumLength(500).WithMessage("Search query must not exceed 500 characters.");
    }
}

public class SearchDocumentsQueryHandler
    : IRequestHandler<SearchDocumentsQuery, Result<IReadOnlyList<SharePointSearchResultDto>>>
{
    private readonly ISharePointService _sharePointService;

    public SearchDocumentsQueryHandler(ISharePointService sharePointService)
    {
        _sharePointService = sharePointService;
    }

    public async Task<Result<IReadOnlyList<SharePointSearchResultDto>>> Handle(
        SearchDocumentsQuery request, CancellationToken cancellationToken)
    {
        var results = await _sharePointService.SearchDocumentsAsync(
            request.Query, cancellationToken);

        return Result<IReadOnlyList<SharePointSearchResultDto>>.Success(results);
    }
}
