using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface ITextSegmentRepository : IRepository<TextSegment>
{
    Task<IReadOnlyList<TextSegment>> GetByDocumentIdAsync(Guid documentId, CancellationToken cancellationToken = default);
}
