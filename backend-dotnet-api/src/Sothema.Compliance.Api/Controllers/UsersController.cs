using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Application.DTOs;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class UsersController : ControllerBase
{
    private readonly ICurrentUserService _currentUserService;

    public UsersController(ICurrentUserService currentUserService)
    {
        _currentUserService = currentUserService;
    }

    [HttpGet("me")]
    public IActionResult GetCurrentUser()
    {
        var profile = new UserProfileDto
        {
            Id = _currentUserService.ObjectId,
            EntraObjectId = _currentUserService.ObjectId,
            DisplayName = _currentUserService.DisplayName,
            Email = _currentUserService.Email,
            Role = _currentUserService.Role,
            CreatedAt = DateTime.UtcNow
        };

        return Ok(profile);
    }
}
