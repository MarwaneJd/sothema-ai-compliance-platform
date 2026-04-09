namespace Sothema.Compliance.Application.DTOs;

public record UserProfileDto
{
    public string ObjectId { get; init; } = string.Empty;
    public string DisplayName { get; init; } = string.Empty;
    public string Email { get; init; } = string.Empty;
    public string Role { get; init; } = string.Empty;
}
