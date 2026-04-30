using System.Security.Claims;
using Microsoft.AspNetCore.Http;
using Sothema.Compliance.Application.Common.Interfaces;

namespace Sothema.Compliance.Infrastructure.Services;

public class CurrentUserService : ICurrentUserService
{
    private readonly IHttpContextAccessor _httpContextAccessor;

    public CurrentUserService(IHttpContextAccessor httpContextAccessor)
    {
        _httpContextAccessor = httpContextAccessor;
    }

    private ClaimsPrincipal? User => _httpContextAccessor.HttpContext?.User;

    public string ObjectId =>
        User?.FindFirstValue("http://schemas.microsoft.com/identity/claims/objectidentifier")
        ?? User?.FindFirstValue("oid")
        ?? string.Empty;

    public string DisplayName =>
        User?.FindFirstValue("name")
        ?? User?.FindFirstValue(ClaimTypes.Name)
        ?? User?.Identity?.Name
        ?? string.Empty;

    public string Email =>
        User?.FindFirstValue("preferred_username")
        ?? User?.FindFirstValue(ClaimTypes.Email)
        ?? User?.FindFirstValue(ClaimTypes.Upn)
        ?? User?.FindFirstValue("upn")
        ?? User?.FindFirstValue("email")
        ?? User?.FindFirstValue("unique_name")
        ?? string.Empty;

    public string Role =>
        User?.FindFirstValue(ClaimTypes.Role)
        ?? User?.FindFirstValue("roles")
        ?? string.Empty;
}
