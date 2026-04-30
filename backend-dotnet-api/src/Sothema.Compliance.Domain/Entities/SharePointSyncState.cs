namespace Sothema.Compliance.Domain.Entities;

public class SharePointSyncState
{
    public int Id { get; set; }
    public string SiteId { get; set; } = string.Empty;
    public string DriveId { get; set; } = string.Empty;
    public string DeltaToken { get; set; } = string.Empty;
    public string? SubscriptionId { get; set; }
    public DateTime? SubscriptionExpiry { get; set; }
    public DateTime LastSyncAt { get; set; }
}
