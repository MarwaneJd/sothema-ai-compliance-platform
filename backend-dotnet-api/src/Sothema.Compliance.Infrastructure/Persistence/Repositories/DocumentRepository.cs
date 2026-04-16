using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class DocumentRepository : RepositoryBase<Document>, IDocumentRepository
{
    public DocumentRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<Document?> GetBySharePointItemIdAsync(
        string sharePointItemId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Include(d => d.TextSegments)
            .Include(d => d.ComplianceAnalyses)
            .FirstOrDefaultAsync(d => d.SharePointItemId == sharePointItemId, cancellationToken);
    }
}
