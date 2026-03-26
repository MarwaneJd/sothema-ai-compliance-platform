using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IAiRequestRepository : IRepository<AiRequest>
{
    Task<IReadOnlyList<AiRequest>> GetByUserQueryIdAsync(Guid userQueryId, CancellationToken cancellationToken = default);
}
