using Sothema.Compliance.Domain.Enums;

namespace Sothema.Compliance.Domain.Entities;

public class User
{
    public Guid Id { get; set; }
    public string EntraObjectId { get; set; } = string.Empty;
    public string DisplayName { get; set; } = string.Empty;
    public string Email { get; set; } = string.Empty;
    public UserRole Role { get; set; }
    public DateTime CreatedAt { get; set; }

    public ICollection<UserQuery> Queries { get; set; } = new List<UserQuery>();
}
