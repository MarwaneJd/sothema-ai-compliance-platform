using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class DocumentConfiguration : IEntityTypeConfiguration<Document>
{
    public void Configure(EntityTypeBuilder<Document> builder)
    {
        builder.HasKey(d => d.Id);

        builder.Property(d => d.SharePointItemId)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(d => d.Title)
            .IsRequired()
            .HasMaxLength(500);

        builder.Property(d => d.SiteId)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(d => d.DriveId)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(d => d.ContentType)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(d => d.FileType)
            .IsRequired()
            .HasMaxLength(50);

        builder.Property(d => d.SharePointUrl)
            .IsRequired()
            .HasMaxLength(2048);

        builder.HasIndex(d => d.SharePointItemId);

        builder.HasMany(d => d.TextSegments)
            .WithOne(ts => ts.Document)
            .HasForeignKey(ts => ts.DocumentId)
            .OnDelete(DeleteBehavior.Cascade);

        builder.HasMany(d => d.ComplianceAnalyses)
            .WithOne(ca => ca.Document)
            .HasForeignKey(ca => ca.DocumentId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
