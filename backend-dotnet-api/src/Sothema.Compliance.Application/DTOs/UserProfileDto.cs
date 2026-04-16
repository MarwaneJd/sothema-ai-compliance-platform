namespace Sothema.Compliance.Application.DTOs;

public record UserProfileDto
{
    public string Id { get; init; } = string.Empty;
    public string EntraObjectId { get; init; } = string.Empty;
    public string DisplayName { get; init; } = string.Empty;
    public string Email { get; init; } = string.Empty;
    public string Role { get; init; } = string.Empty;
    public DateTime CreatedAt { get; init; }
}
