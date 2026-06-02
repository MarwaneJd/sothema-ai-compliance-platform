namespace Sothema.Compliance.Domain.Entities;

public class Document
{
    public Guid Id { get; set; }
    public string SharePointItemId { get; set; } = string.Empty;
    public string Title { get; set; } = string.Empty;
    public string SiteId { get; set; } = string.Empty;
    public string DriveId { get; set; } = string.Empty;
    public string ContentType { get; set; } = string.Empty;
    public string FileType { get; set; } = string.Empty;
    public string SharePointUrl { get; set; } = string.Empty;
    public DateTime UploadedAt { get; set; }

    /// <summary>
    /// Content identity from SharePoint (quickXorHash / cTag / eTag). Used by the
    /// delta sync to skip items whose content hasn't actually changed, instead of
    /// re-classifying them as Modified and re-indexing them.
    /// </summary>
    public string? ContentHash { get; set; }

    public ICollection<TextSegment> TextSegments { get; set; } = new List<TextSegment>();
    public ICollection<ComplianceAnalysis> ComplianceAnalyses { get; set; } = new List<ComplianceAnalysis>();
}
