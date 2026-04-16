using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Sothema.Compliance.Application.Common.Interfaces;
using Sothema.Compliance.Domain.Interfaces;
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
            // Production: register real SharePointService with GraphServiceClient
            // Requires Microsoft.Identity.Web.MicrosoftGraph and Entra ID configuration
            services.AddSingleton<ISharePointService, StubSharePointService>();
            // TODO: Replace with real SharePointService when credentials are available
            // services.AddScoped<ISharePointService, SharePointService>();
        }

        // Current User
        services.AddHttpContextAccessor();
        services.AddScoped<ICurrentUserService, CurrentUserService>();

        return services;
    }
}
