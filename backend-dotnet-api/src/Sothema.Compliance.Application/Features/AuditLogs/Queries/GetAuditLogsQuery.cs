using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.AuditLogs.Queries;

public record GetAuditLogsQuery : IRequest<Result<PaginatedList<AuditLogDto>>>
{
    public int Page { get; init; } = 1;
    public int PageSize { get; init; } = 50;
    public string? EntityType { get; init; }
    public string? EntityId { get; init; }
}

public class GetAuditLogsQueryHandler
    : IRequestHandler<GetAuditLogsQuery, Result<PaginatedList<AuditLogDto>>>
{
    private readonly IAuditLogRepository _auditLogRepository;
    private readonly IUserRepository _userRepository;
    private readonly IMapper _mapper;

    public GetAuditLogsQueryHandler(
        IAuditLogRepository auditLogRepository,
        IUserRepository userRepository,
        IMapper mapper)
    {
        _auditLogRepository = auditLogRepository;
        _userRepository = userRepository;
        _mapper = mapper;
    }

    public async Task<Result<PaginatedList<AuditLogDto>>> Handle(
        GetAuditLogsQuery request, CancellationToken cancellationToken)
    {
        IReadOnlyList<AuditLog> logs;

        if (!string.IsNullOrEmpty(request.EntityType)
            && !string.IsNullOrEmpty(request.EntityId))
        {
            logs = await _auditLogRepository.GetByEntityAsync(
                request.EntityType, request.EntityId, cancellationToken);
        }
        else
        {
            logs = await _auditLogRepository.GetAllAsync(cancellationToken);
        }

        var totalCount = logs.Count;

        var pagedItems = logs
            .OrderByDescending(l => l.Timestamp)
            .Skip((request.Page - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        // Resolve display names in one query for all distinct user IDs on this page.
        // UserId is the Entra object ID for human users; system actors (e.g. "ai-service")
        // won't match any User row and fall back to displaying the raw UserId.
        var objectIds = pagedItems
            .Select(l => l.UserId)
            .Where(id => !string.IsNullOrEmpty(id))
            .Distinct()
            .ToList();

        var namesByObjectId = await _userRepository
            .GetDisplayNamesByObjectIdsAsync(objectIds, cancellationToken);

        var dtos = pagedItems.Select(log =>
        {
            var dto = _mapper.Map<AuditLogDto>(log);
            var resolved = namesByObjectId.TryGetValue(log.UserId, out var name) ? name : log.UserId;
            return dto with { UserName = resolved };
        }).ToList();

        return Result<PaginatedList<AuditLogDto>>.Success(
            new PaginatedList<AuditLogDto>(dtos, totalCount, request.Page, request.PageSize));
    }
}
