namespace Sothema.Compliance.Domain.Entities;

public class UserQuery
{
    public Guid Id { get; set; }
    public Guid UserId { get; set; }
    public string Question { get; set; } = string.Empty;
    public string? Response { get; set; }
    public Guid? AgentId { get; set; }
    public DateTime CreatedAt { get; set; }

    public User User { get; set; } = null!;
    public Agent? Agent { get; set; }
}
