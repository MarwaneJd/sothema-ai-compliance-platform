using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class ComplianceAnalysisRepository : RepositoryBase<ComplianceAnalysis>, IComplianceAnalysisRepository
{
    public ComplianceAnalysisRepository(ComplianceDbContext context) : base(context)
    {
    }

    public override async Task<IReadOnlyList<ComplianceAnalysis>> GetAllAsync(
        CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(ca => ca.Document)
            .OrderByDescending(ca => ca.AnalyzedAt)
            .ToListAsync(cancellationToken);
    }

    public override async Task<ComplianceAnalysis?> GetByIdAsync(
        Guid id, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(ca => ca.Document)
            .FirstOrDefaultAsync(ca => ca.Id == id, cancellationToken);
    }

    public async Task<IReadOnlyList<ComplianceAnalysis>> GetByDocumentIdAsync(
        Guid documentId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(ca => ca.Document)
            .Where(ca => ca.DocumentId == documentId)
            .OrderByDescending(ca => ca.AnalyzedAt)
            .ToListAsync(cancellationToken);
    }
}
