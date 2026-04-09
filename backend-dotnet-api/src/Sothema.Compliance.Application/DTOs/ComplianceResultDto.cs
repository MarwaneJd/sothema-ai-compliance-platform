namespace Sothema.Compliance.Application.DTOs;

public record ComplianceResultDto
{
    public Guid Id { get; init; }
    public Guid DocumentId { get; init; }
    public string DocumentTitle { get; init; } = string.Empty;
    public double Score { get; init; }
    public string Summary { get; init; } = string.Empty;
    public string? Details { get; init; }
    public string Status { get; init; } = string.Empty;
    public DateTime AnalyzedAt { get; init; }
}
