using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class AiRequestConfiguration : IEntityTypeConfiguration<AiRequest>
{
    public void Configure(EntityTypeBuilder<AiRequest> builder)
    {
        builder.HasKey(ar => ar.Id);

        builder.Property(ar => ar.Question)
            .IsRequired()
            .HasMaxLength(2000);

        builder.Property(ar => ar.Response)
            .HasColumnType("nvarchar(max)");

        builder.HasOne(ar => ar.UserQuery)
            .WithMany()
            .HasForeignKey(ar => ar.UserQueryId)
            .OnDelete(DeleteBehavior.SetNull);

        builder.HasMany(ar => ar.ContextSegments)
            .WithOne(ars => ars.AiRequest)
            .HasForeignKey(ars => ars.AiRequestId)
            .OnDelete(DeleteBehavior.Cascade);
    }
}
