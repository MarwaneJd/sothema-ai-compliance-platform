using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IUserQueryRepository : IRepository<UserQuery>
{
    Task<IReadOnlyList<UserQuery>> GetByUserIdAsync(Guid userId, CancellationToken cancellationToken = default);
}
