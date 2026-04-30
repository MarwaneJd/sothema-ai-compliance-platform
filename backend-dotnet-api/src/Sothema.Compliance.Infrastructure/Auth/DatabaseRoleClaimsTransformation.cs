using System.Security.Claims;
using Microsoft.AspNetCore.Authentication;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Enums;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Auth;

public class DatabaseRoleClaimsTransformation : IClaimsTransformation
{
    private readonly IUserRepository _userRepository;
    private readonly IConfiguration _configuration;
    private readonly ILogger<DatabaseRoleClaimsTransformation> _logger;

    public DatabaseRoleClaimsTransformation(
        IUserRepository userRepository,
        IConfiguration configuration,
        ILogger<DatabaseRoleClaimsTransformation> logger)
    {
        _userRepository = userRepository;
        _configuration = configuration;
        _logger = logger;
    }

    public async Task<ClaimsPrincipal> TransformAsync(ClaimsPrincipal principal)
    {
        if (principal.Identity is not { IsAuthenticated: true })
        {
            return principal;
        }

        if (principal.HasClaim(c => c.Type == ClaimTypes.Role || c.Type == "roles"))
        {
            return principal;
        }

        var objectId =
            principal.FindFirstValue("http://schemas.microsoft.com/identity/claims/objectidentifier")
            ?? principal.FindFirstValue("oid");

        if (string.IsNullOrEmpty(objectId))
        {
            return principal;
        }

        var displayName =
            principal.FindFirstValue("name")
            ?? principal.FindFirstValue(ClaimTypes.Name)
            ?? principal.Identity?.Name
            ?? string.Empty;

        var email =
            principal.FindFirstValue("preferred_username")
            ?? principal.FindFirstValue(ClaimTypes.Email)
            ?? principal.FindFirstValue(ClaimTypes.Upn)
            ?? principal.FindFirstValue("upn")
            ?? principal.FindFirstValue("email")
            ?? principal.FindFirstValue("unique_name")
            ?? string.Empty;

        var user = await _userRepository.GetByEntraObjectIdAsync(objectId);

        if (user is null)
        {
            var defaultRoleName = _configuration["Authorization:DefaultNewUserRole"] ?? "Viewer";
            if (!Enum.TryParse<UserRole>(defaultRoleName, ignoreCase: true, out var defaultRole))
            {
                defaultRole = UserRole.Viewer;
            }

            user = new User
            {
                Id = Guid.NewGuid(),
                EntraObjectId = objectId,
                DisplayName = displayName,
                Email = email,
                Role = defaultRole,
                CreatedAt = DateTime.UtcNow,
            };

            await _userRepository.AddAsync(user);
            _logger.LogInformation(
                "Provisioned new user {Email} ({ObjectId}) with role {Role}",
                email, objectId, defaultRole);
        }
        else if (string.IsNullOrWhiteSpace(user.Email) && !string.IsNullOrWhiteSpace(email))
        {
            user.Email = email;
            if (string.IsNullOrWhiteSpace(user.DisplayName) && !string.IsNullOrWhiteSpace(displayName))
            {
                user.DisplayName = displayName;
            }
            await _userRepository.UpdateAsync(user);
            _logger.LogInformation("Backfilled email for user {ObjectId}", objectId);
        }

        var identity = (ClaimsIdentity)principal.Identity!;
        identity.AddClaim(new Claim(ClaimTypes.Role, user.Role.ToString()));

        return principal;
    }
}
