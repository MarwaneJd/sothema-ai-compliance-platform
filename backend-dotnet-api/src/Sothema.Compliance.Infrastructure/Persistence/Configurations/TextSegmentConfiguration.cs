using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class TextSegmentConfiguration : IEntityTypeConfiguration<TextSegment>
{
    public void Configure(EntityTypeBuilder<TextSegment> builder)
    {
        builder.HasKey(ts => ts.Id);

        builder.Property(ts => ts.Content)
            .IsRequired()
            .HasColumnType("nvarchar(max)");

        builder.Property(ts => ts.VectorStoreId)
            .HasMaxLength(256);

        builder.HasIndex(ts => ts.DocumentId);

        builder.HasMany(ts => ts.AiRequestSegments)
            .WithOne(ars => ars.TextSegment)
            .HasForeignKey(ars => ars.TextSegmentId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
