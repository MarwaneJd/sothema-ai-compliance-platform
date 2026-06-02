namespace Sothema.Compliance.Application.DTOs;

public record SharePointSearchResultDto
{
    public string SharePointItemId { get; init; } = string.Empty;
    public string Title { get; init; } = string.Empty;
    public string SiteId { get; init; } = string.Empty;
    public string DriveId { get; init; } = string.Empty;
    public string ContentType { get; init; } = string.Empty;
    public string FileType { get; init; } = string.Empty;
    public string SharePointUrl { get; init; } = string.Empty;
    public DateTime? LastModified { get; init; }
    public string? ContentHash { get; init; }
}
