using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class AgentRepository : RepositoryBase<Agent>, IAgentRepository
{
    public AgentRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<IReadOnlyList<Agent>> GetByTaskTypeAsync(
        string taskType, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(a => a.TaskType == taskType)
            .ToListAsync(cancellationToken);
    }
}
