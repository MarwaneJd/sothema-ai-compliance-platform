using Microsoft.EntityFrameworkCore;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence;

public class ComplianceDbContext : DbContext
{
    public ComplianceDbContext(DbContextOptions<ComplianceDbContext> options)
        : base(options)
    {
    }

    public DbSet<Document> Documents => Set<Document>();
    public DbSet<ComplianceAnalysis> ComplianceAnalyses => Set<ComplianceAnalysis>();
    public DbSet<User> Users => Set<User>();
    public DbSet<AuditLog> AuditLogs => Set<AuditLog>();
    public DbSet<TextSegment> TextSegments => Set<TextSegment>();
    public DbSet<UserQuery> UserQueries => Set<UserQuery>();
    public DbSet<Agent> Agents => Set<Agent>();
    public DbSet<AiRequest> AiRequests => Set<AiRequest>();
    public DbSet<AiRequestSegment> AiRequestSegments => Set<AiRequestSegment>();
    public DbSet<SharePointSyncState> SharePointSyncStates => Set<SharePointSyncState>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.ApplyConfigurationsFromAssembly(typeof(ComplianceDbContext).Assembly);
        base.OnModelCreating(modelBuilder);
    }
}
