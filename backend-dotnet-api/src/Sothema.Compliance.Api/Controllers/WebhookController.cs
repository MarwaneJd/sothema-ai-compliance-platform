using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Options;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Infrastructure.Services;

namespace Sothema.Compliance.Api.Controllers;

[ApiController]
[AllowAnonymous]
[Route("api/webhooks/sharepoint")]
public class WebhookController : ControllerBase
{
    private readonly IServiceScopeFactory _scopeFactory;
    private readonly SharePointSyncOptions _options;
    private readonly ILogger<WebhookController> _logger;

    public WebhookController(
        IServiceScopeFactory scopeFactory,
        IOptions<SharePointSyncOptions> options,
        ILogger<WebhookController> logger)
    {
        _scopeFactory = scopeFactory;
        _options = options.Value;
        _logger = logger;
    }

    [HttpPost]
    public async Task<IActionResult> HandleNotification(
        [FromQuery] string? validationToken,
        CancellationToken cancellationToken)
    {
        // Graph validation handshake — must return the token as text/plain within 10s.
        if (!string.IsNullOrEmpty(validationToken))
        {
            _logger.LogInformation("WebhookController: Graph validation handshake received.");
            return Content(validationToken, "text/plain");
        }

        using var reader = new StreamReader(Request.Body, Encoding.UTF8);
        var body = await reader.ReadToEndAsync(cancellationToken);

        if (string.IsNullOrWhiteSpace(body))
        {
            return Accepted();
        }

        if (!ClientStateIsValid(body))
        {
            _logger.LogWarning(
                "WebhookController: received notification with invalid clientState — ignoring.");
            return Accepted();
        }

        // Fire-and-forget sync so Graph sees a fast 202.
        _ = Task.Run(async () =>
        {
            try
            {
                using var scope = _scopeFactory.CreateScope();
                var processor = scope.ServiceProvider.GetRequiredService<ISyncProcessor>();
                await processor.ProcessChangesAsync(CancellationToken.None);
            }
            catch (Exception ex)
            {
                _logger.LogError(ex,
                    "WebhookController: background sync triggered by webhook failed.");
            }
        });

        return Accepted();
    }

    private bool ClientStateIsValid(string rawBody)
    {
        if (string.IsNullOrEmpty(_options.WebhookClientState))
        {
            return false;
        }

        try
        {
            using var doc = JsonDocument.Parse(rawBody);
            if (!doc.RootElement.TryGetProperty("value", out var values))
            {
                return false;
            }

            var expected = Encoding.UTF8.GetBytes(_options.WebhookClientState);

            foreach (var notification in values.EnumerateArray())
            {
                if (!notification.TryGetProperty("clientState", out var clientStateElement))
                    return false;

                var clientState = clientStateElement.GetString();
                if (string.IsNullOrEmpty(clientState))
                    return false;

                var actual = Encoding.UTF8.GetBytes(clientState);
                if (!CryptographicOperations.FixedTimeEquals(expected, actual))
                    return false;
            }

            return true;
        }
        catch (JsonException)
        {
            return false;
        }
    }
}
