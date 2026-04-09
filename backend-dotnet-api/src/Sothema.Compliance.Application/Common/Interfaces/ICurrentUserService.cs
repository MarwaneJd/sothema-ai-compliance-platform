namespace Sothema.Compliance.Application.Common.Interfaces;

public interface ICurrentUserService
{
    string ObjectId { get; }
    string DisplayName { get; }
    string Email { get; }
    string Role { get; }
}
