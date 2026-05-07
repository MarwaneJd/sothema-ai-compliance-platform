using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IUserRepository : IRepository<User>
{
    Task<User?> GetByEntraObjectIdAsync(string entraObjectId, CancellationToken cancellationToken = default);
    Task<IReadOnlyDictionary<string, string>> GetDisplayNamesByObjectIdsAsync(IEnumerable<string> objectIds, CancellationToken cancellationToken = default);
}
