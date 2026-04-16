using Microsoft.AspNetCore.Mvc;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class HealthController : ControllerBase
{
    [HttpGet]
    public IActionResult Get()
    {
        return Ok(new
        {
            Status = "Healthy",
            Timestamp = DateTime.UtcNow,
            Service = "Sothema.Compliance.Api"
        });
    }
}
