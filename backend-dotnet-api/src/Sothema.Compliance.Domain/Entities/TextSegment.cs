namespace Sothema.Compliance.Domain.Entities;

public class TextSegment
{
    public Guid Id { get; set; }
    public Guid DocumentId { get; set; }
    public string Content { get; set; } = string.Empty;
    public int ChunkIndex { get; set; }
    public string? VectorStoreId { get; set; }
    public DateTime CreatedAt { get; set; }

    public Document Document { get; set; } = null!;
    public ICollection<AiRequestSegment> AiRequestSegments { get; set; } = new List<AiRequestSegment>();
}
