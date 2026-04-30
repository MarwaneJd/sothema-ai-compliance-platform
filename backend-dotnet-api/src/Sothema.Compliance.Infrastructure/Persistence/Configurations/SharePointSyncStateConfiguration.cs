using Microsoft.EntityFrameworkCore;
using Microsoft.EntityFrameworkCore.Metadata.Builders;
using Sothema.Compliance.Domain.Entities;

namespace Sothema.Compliance.Infrastructure.Persistence.Configurations;

public class SharePointSyncStateConfiguration : IEntityTypeConfiguration<SharePointSyncState>
{
    public void Configure(EntityTypeBuilder<SharePointSyncState> builder)
    {
        builder.ToTable("SharePointSyncStates");

        builder.HasKey(s => s.Id);

        builder.Property(s => s.Id)
            .ValueGeneratedOnAdd();

        builder.Property(s => s.SiteId)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(s => s.DriveId)
            .IsRequired()
            .HasMaxLength(256);

        builder.Property(s => s.DeltaToken)
            .IsRequired();

        builder.Property(s => s.SubscriptionId)
            .HasMaxLength(128);

        builder.Property(s => s.SubscriptionExpiry);

        builder.Property(s => s.LastSyncAt)
            .IsRequired();

        builder.HasIndex(s => new { s.SiteId, s.DriveId })
            .IsUnique();
    }
}
