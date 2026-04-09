using AutoMapper;
using MediatR;
using Sothema.Compliance.Application.Common.Models;
using Sothema.Compliance.Application.DTOs;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Application.Features.AuditLogs.Queries;

public record GetAuditLogsQuery : IRequest<Result<PaginatedList<AuditLogDto>>>
{
    public int PageIndex { get; init; } = 1;
    public int PageSize { get; init; } = 50;
    public string? EntityType { get; init; }
    public string? EntityId { get; init; }
}

public class GetAuditLogsQueryHandler
    : IRequestHandler<GetAuditLogsQuery, Result<PaginatedList<AuditLogDto>>>
{
    private readonly IAuditLogRepository _auditLogRepository;
    private readonly IMapper _mapper;

    public GetAuditLogsQueryHandler(IAuditLogRepository auditLogRepository, IMapper mapper)
    {
        _auditLogRepository = auditLogRepository;
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
            .Skip((request.PageIndex - 1) * request.PageSize)
            .Take(request.PageSize)
            .ToList();

        var dtos = _mapper.Map<List<AuditLogDto>>(pagedItems);

        return Result<PaginatedList<AuditLogDto>>.Success(
            new PaginatedList<AuditLogDto>(dtos, totalCount, request.PageIndex, request.PageSize));
    }
}
