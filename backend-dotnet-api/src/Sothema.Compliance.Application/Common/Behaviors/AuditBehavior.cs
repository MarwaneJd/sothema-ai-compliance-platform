using MediatR;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Common.Behaviors;

public interface ICommand<T> : IRequest<T>;

public class AuditBehavior<TRequest, TResponse> : IPipelineBehavior<TRequest, TResponse>
    where TRequest : IRequest<TResponse>
{
    private readonly IAuditLogRepository _auditLogRepository;
    private readonly ICurrentUserService _currentUserService;

    public AuditBehavior(
        IAuditLogRepository auditLogRepository,
        ICurrentUserService currentUserService)
    {
        _auditLogRepository = auditLogRepository;
        _currentUserService = currentUserService;
    }

    public async Task<TResponse> Handle(
        TRequest request,
        RequestHandlerDelegate<TResponse> next,
        CancellationToken cancellationToken)
    {
        var response = await next();

        if (request is ICommand<TResponse>)
        {
            var auditLog = new AuditLog
            {
                Id = Guid.NewGuid(),
                UserId = _currentUserService.ObjectId,
                Action = typeof(TRequest).Name,
                EntityType = typeof(TRequest).Name,
                EntityId = ExtractEntityId(request),
                Timestamp = DateTime.UtcNow,
                Details = null
            };

            await _auditLogRepository.AddAsync(auditLog, cancellationToken);
        }

        return response;
    }

    private static string ExtractEntityId(TRequest request)
    {
        var prop = typeof(TRequest).GetProperty("DocumentId")
                ?? typeof(TRequest).GetProperty("Id");
        return prop?.GetValue(request)?.ToString() ?? string.Empty;
    }
}
