using Azure.Identity;
using Microsoft.AspNetCore.Authentication;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Graph;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Domain.Interfaces;
using Sothema.Compliance.Infrastructure.Auth;
using Sothema.Compliance.Infrastructure.Persistence;
using Sothema.Compliance.Infrastructure.Persistence.Repositories;
using Sothema.Compliance.Infrastructure.Services;

namespace Sothema.Compliance.Infrastructure;

public static class DependencyInjection
{
    public static IServiceCollection AddInfrastructure(
        this IServiceCollection services, IConfiguration configuration)
    {
        // DbContext
        services.AddDbContext<ComplianceDbContext>(options =>
            options.UseSqlServer(
                configuration.GetConnectionString("DefaultConnection"),
                b => b.MigrationsAssembly(typeof(ComplianceDbContext).Assembly.FullName)));

        // Repositories
        services.AddScoped<IDocumentRepository, DocumentRepository>();
        services.AddScoped<IComplianceAnalysisRepository, ComplianceAnalysisRepository>();
        services.AddScoped<IUserRepository, UserRepository>();
        services.AddScoped<IAuditLogRepository, AuditLogRepository>();
        services.AddScoped<ITextSegmentRepository, TextSegmentRepository>();
        services.AddScoped<IUserQueryRepository, UserQueryRepository>();
        services.AddScoped<IAiRequestRepository, AiRequestRepository>();
        services.AddScoped<IAgentRepository, AgentRepository>();

        // AI Service (Python backend) — typed HttpClient with API key
        var aiApiKey = configuration["AiService:ApiKey"] ?? "";
        services.AddHttpClient<IAiService, AiServiceClient>(client =>
        {
            var baseUrl = configuration["AiService:BaseUrl"] ?? "http://localhost:8000/";
            if (!baseUrl.EndsWith('/')) baseUrl += "/";
            client.BaseAddress = new Uri(baseUrl);
            client.Timeout = TimeSpan.FromMinutes(5);
            if (!string.IsNullOrEmpty(aiApiKey))
            {
                client.DefaultRequestHeaders.Add("X-API-Key", aiApiKey);
            }
        });

        // SharePoint — use stub when no credentials configured
        var useDevAuth = configuration.GetValue<bool>("UseDevAuth");
        if (useDevAuth)
        {
            services.AddSingleton<ISharePointService, StubSharePointService>();
        }
        else
        {
            services.AddScoped<ISharePointService, SharePointService>();
        }

        // Current User
        services.AddHttpContextAccessor();
        services.AddScoped<ICurrentUserService, CurrentUserService>();

        // DB-backed role resolution (adds ClaimTypes.Role from Users table on each authenticated request)
        services.AddScoped<IClaimsTransformation, DatabaseRoleClaimsTransformation>();

        // SharePoint sync (webhooks + delta polling)
        services.Configure<SharePointSyncOptions>(
            configuration.GetSection(SharePointSyncOptions.SectionName));

        var syncEnabled = configuration.GetValue<bool>(
            $"{SharePointSyncOptions.SectionName}:Enabled");

        if (syncEnabled)
        {
            // App-only Graph client for background services (no user context).
            // Uses client-credentials flow with Sites.ReadWrite.All app permission.
            services.AddSingleton<AppGraphClient>(sp =>
            {
                var tenantId = configuration["AzureAd:TenantId"]
                    ?? throw new InvalidOperationException("AzureAd:TenantId is required for SharePoint sync.");
                var clientId = configuration["AzureAd:ClientId"]
                    ?? throw new InvalidOperationException("AzureAd:ClientId is required for SharePoint sync.");
                var clientSecret = configuration["AzureAd:ClientSecret"]
                    ?? throw new InvalidOperationException("AzureAd:ClientSecret (user-secret) is required for SharePoint sync.");

                var credential = new ClientSecretCredential(tenantId, clientId, clientSecret);
                var graph = new GraphServiceClient(credential,
                    new[] { "https://graph.microsoft.com/.default" });
                return new AppGraphClient(graph);
            });

            services.AddScoped<ISyncProcessor, SharePointSyncProcessor>();
            services.AddHostedService<DeltaSyncService>();
            services.AddHostedService<SubscriptionRenewalService>();
        }

        return services;
    }
}
