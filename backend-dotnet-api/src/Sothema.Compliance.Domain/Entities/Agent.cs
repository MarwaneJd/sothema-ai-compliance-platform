namespace Sothema.Compliance.Domain.Entities;

public class Agent
{
    public Guid Id { get; set; }
    public string Name { get; set; } = string.Empty;
    public string TaskType { get; set; } = string.Empty;
    public bool IsActive { get; set; }

    public ICollection<UserQuery> ProcessedQueries { get; set; } = new List<UserQuery>();
}
