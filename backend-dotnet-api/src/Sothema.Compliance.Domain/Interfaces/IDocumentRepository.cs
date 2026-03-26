using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IDocumentRepository : IRepository<Document>
{
    Task<Document?> GetBySharePointItemIdAsync(string sharePointItemId, CancellationToken cancellationToken = default);
}
