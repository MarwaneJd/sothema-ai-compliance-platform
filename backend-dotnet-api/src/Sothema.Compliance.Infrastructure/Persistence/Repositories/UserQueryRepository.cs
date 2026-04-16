using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class UserQueryRepository : RepositoryBase<UserQuery>, IUserQueryRepository
{
    public UserQueryRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<IReadOnlyList<UserQuery>> GetByUserIdAsync(
        Guid userId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(uq => uq.Agent)
            .Where(uq => uq.UserId == userId)
            .OrderByDescending(uq => uq.CreatedAt)
            .ToListAsync(cancellationToken);
    }
}
