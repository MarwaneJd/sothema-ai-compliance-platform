namespace Sothema.Compliance.Infrastructure.Services;

public class SharePointSyncOptions
{
    public const string SectionName = "SharePointSync";

    public bool Enabled { get; set; } = false;
    public string SiteId { get; set; } = string.Empty;
    public string DriveId { get; set; } = string.Empty;
    public int PollingIntervalMinutes { get; set; } = 20;
    public int BatchSize { get; set; } = 5;
    public int BatchDelayMilliseconds { get; set; } = 2000;
    public string WebhookClientState { get; set; } = string.Empty;
    public string WebhookBaseUrl { get; set; } = string.Empty;
    public int SubscriptionLifetimeDays { get; set; } = 29;
    public int RenewalThresholdHours { get; set; } = 48;
}
