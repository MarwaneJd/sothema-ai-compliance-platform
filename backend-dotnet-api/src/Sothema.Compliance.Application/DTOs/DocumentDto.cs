namespace Sothema.Compliance.Application.DTOs;

public record DocumentDto
{
    public Guid Id { get; init; }
    public string SharePointItemId { get; init; } = string.Empty;
    public string Title { get; init; } = string.Empty;
    public string SiteId { get; init; } = string.Empty;
    public string DriveId { get; init; } = string.Empty;
    public string ContentType { get; init; } = string.Empty;
    public string FileType { get; init; } = string.Empty;
    public string SharePointUrl { get; init; } = string.Empty;
    public DateTime UploadedAt { get; init; }
    public int TextSegmentCount { get; init; }
    public int AnalysisCount { get; init; }
}
