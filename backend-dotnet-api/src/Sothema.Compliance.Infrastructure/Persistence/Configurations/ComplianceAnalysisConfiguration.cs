using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class ComplianceAnalysisConfiguration : IEntityTypeConfiguration<ComplianceAnalysis>
{
    public void Configure(EntityTypeBuilder<ComplianceAnalysis> builder)
    {
        builder.HasKey(ca => ca.Id);

        builder.Property(ca => ca.Summary)
            .IsRequired()
            .HasColumnType("nvarchar(max)");

        builder.Property(ca => ca.Details)
            .HasColumnType("nvarchar(max)");

        builder.Property(ca => ca.Status)
            .IsRequired();

        builder.HasIndex(ca => new { ca.DocumentId, ca.AnalyzedAt });
    }
}
