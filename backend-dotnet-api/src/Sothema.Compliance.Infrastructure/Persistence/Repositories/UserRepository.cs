using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class UserRepository : RepositoryBase<User>, IUserRepository
{
    public UserRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<User?> GetByEntraObjectIdAsync(
        string entraObjectId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .FirstOrDefaultAsync(u => u.EntraObjectId == entraObjectId, cancellationToken);
    }

    public async Task<IReadOnlyDictionary<string, string>> GetDisplayNamesByObjectIdsAsync(
        IEnumerable<string> objectIds, CancellationToken cancellationToken = default)
    {
        var ids = objectIds.ToList();
        return await DbSet
            .Where(u => ids.Contains(u.EntraObjectId))
            .ToDictionaryAsync(u => u.EntraObjectId, u => u.DisplayName, cancellationToken);
    }
}
