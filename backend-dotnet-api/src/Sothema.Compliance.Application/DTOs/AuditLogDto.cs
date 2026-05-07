namespace Sothema.Compliance.Application.DTOs;

public record AuditLogDto
{
    public Guid Id { get; init; }
    public string UserId { get; init; } = string.Empty;
    public string Action { get; init; } = string.Empty;
    public string EntityType { get; init; } = string.Empty;
    public string EntityId { get; init; } = string.Empty;
    public DateTime Timestamp { get; init; }
    public string? Details { get; init; }
    public string? UserName { get; init; }
}
