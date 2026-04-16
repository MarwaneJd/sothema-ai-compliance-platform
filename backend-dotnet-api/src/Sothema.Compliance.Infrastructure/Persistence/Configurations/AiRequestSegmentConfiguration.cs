using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class AiRequestSegmentConfiguration : IEntityTypeConfiguration<AiRequestSegment>
{
    public void Configure(EntityTypeBuilder<AiRequestSegment> builder)
    {
        builder.HasKey(ars => new { ars.AiRequestId, ars.TextSegmentId });
    }
}
