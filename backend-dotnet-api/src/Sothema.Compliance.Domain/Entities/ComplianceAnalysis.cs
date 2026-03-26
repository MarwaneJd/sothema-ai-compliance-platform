using Sothema.Compliance.Domain.Enums;

namespace Sothema.Compliance.Domain.Entities;

public class ComplianceAnalysis
{
    public Guid Id { get; set; }
    public Guid DocumentId { get; set; }
    public double Score { get; set; }
    public string Summary { get; set; } = string.Empty;
    public string? Details { get; set; }
    public AnalysisStatus Status { get; set; }
    public DateTime AnalyzedAt { get; set; }

    public Document Document { get; set; } = null!;
}
