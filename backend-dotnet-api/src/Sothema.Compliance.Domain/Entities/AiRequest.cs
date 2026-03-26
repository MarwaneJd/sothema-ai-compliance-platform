namespace Sothema.Compliance.Domain.Entities;

public class AiRequest
{
    public Guid Id { get; set; }
    public Guid? UserQueryId { get; set; }
    public string Question { get; set; } = string.Empty;
    public string? Response { get; set; }
    public DateTime CreatedAt { get; set; }

    public UserQuery? UserQuery { get; set; }
    public ICollection<AiRequestSegment> ContextSegments { get; set; } = new List<AiRequestSegment>();
}
