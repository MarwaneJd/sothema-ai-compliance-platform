using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace Sothema.Compliance.Infrastructure.Migrations
{
    /// <inheritdoc />
    public partial class AddDocumentContentHash : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "ContentHash",
                table: "Documents",
                type: "nvarchar(256)",
                maxLength: 256,
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "ContentHash",
                table: "Documents");
        }
    }
}
