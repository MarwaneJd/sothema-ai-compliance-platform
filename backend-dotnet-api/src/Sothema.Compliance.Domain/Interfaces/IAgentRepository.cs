using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IAgentRepository : IRepository<Agent>
{
    Task<IReadOnlyList<Agent>> GetByTaskTypeAsync(string taskType, CancellationToken cancellationToken = default);
}
