using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class AiRequestRepository : RepositoryBase<AiRequest>, IAiRequestRepository
{
    public AiRequestRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<IReadOnlyList<AiRequest>> GetByUserQueryIdAsync(
        Guid userQueryId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(ar => ar.ContextSegments)
                .ThenInclude(cs => cs.TextSegment)
            .Where(ar => ar.UserQueryId == userQueryId)
            .OrderByDescending(ar => ar.CreatedAt)
            .ToListAsync(cancellationToken);
    }
}
