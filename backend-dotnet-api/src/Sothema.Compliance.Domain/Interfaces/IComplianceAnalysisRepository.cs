using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Domain.Interfaces;

public interface IComplianceAnalysisRepository : IRepository<ComplianceAnalysis>
{
    Task<IReadOnlyList<ComplianceAnalysis>> GetByDocumentIdAsync(Guid documentId, CancellationToken cancellationToken = default);
}
