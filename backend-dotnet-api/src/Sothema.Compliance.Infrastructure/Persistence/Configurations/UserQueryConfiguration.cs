using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class UserQueryConfiguration : IEntityTypeConfiguration<UserQuery>
{
    public void Configure(EntityTypeBuilder<UserQuery> builder)
    {
        builder.HasKey(uq => uq.Id);

        builder.Property(uq => uq.Question)
            .IsRequired()
            .HasMaxLength(2000);

        builder.Property(uq => uq.Response)
            .HasColumnType("nvarchar(max)");

        builder.HasOne(uq => uq.Agent)
            .WithMany(a => a.ProcessedQueries)
            .HasForeignKey(uq => uq.AgentId)
            .OnDelete(DeleteBehavior.SetNull);
    }
}
