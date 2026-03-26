namespace Sothema.Compliance.Domain.Entities;

public class AiRequestSegment
{
    public Guid AiRequestId { get; set; }
    public Guid TextSegmentId { get; set; }
    public double? RelevanceScore { get; set; }

    public AiRequest AiRequest { get; set; } = null!;
    public TextSegment TextSegment { get; set; } = null!;
}
