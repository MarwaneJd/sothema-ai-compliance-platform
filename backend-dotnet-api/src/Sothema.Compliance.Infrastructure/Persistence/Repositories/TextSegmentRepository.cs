using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;
using Sothema.Compliance.Domain.Interfaces;

namespace Sothema.Compliance.Infrastructure.Persistence.Repositories;

public class TextSegmentRepository : RepositoryBase<TextSegment>, ITextSegmentRepository
{
    public TextSegmentRepository(ComplianceDbContext context) : base(context)
    {
    }

    public async Task<IReadOnlyList<TextSegment>> GetByDocumentIdAsync(
        Guid documentId, CancellationToken cancellationToken = default)
    {
        return await DbSet
            .Where(ts => ts.DocumentId == documentId)
            .OrderBy(ts => ts.ChunkIndex)
            .ToListAsync(cancellationToken);
    }
}
