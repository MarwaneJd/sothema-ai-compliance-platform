# ───────────────────────────────────────────────────
# Stage 1: build
# ───────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy only project files first for layer-cached restore
COPY Directory.Build.props .
COPY Sothema.Compliance.sln .
COPY src/Sothema.Compliance.Api/*.csproj            src/Sothema.Compliance.Api/
COPY src/Sothema.Compliance.Application/*.csproj    src/Sothema.Compliance.Application/
COPY src/Sothema.Compliance.Domain/*.csproj         src/Sothema.Compliance.Domain/
COPY src/Sothema.Compliance.Infrastructure/*.csproj src/Sothema.Compliance.Infrastructure/
COPY tests/Sothema.Compliance.Tests/*.csproj        tests/Sothema.Compliance.Tests/
RUN dotnet restore Sothema.Compliance.sln

# Now copy source and publish
COPY . .
RUN dotnet publish src/Sothema.Compliance.Api/Sothema.Compliance.Api.csproj \
    -c Release \
    -o /app/publish \
    --no-restore

# ───────────────────────────────────────────────────
# Stage 2: runtime (alpine — small, debuggable, broad compatibility)
# ───────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/aspnet:8.0-alpine AS runtime

# Alpine has no ICU data by default; SqlClient requires culture support.
RUN apk add --no-cache icu-libs
ENV DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=false

# aspnet:8.0-alpine ships a non-root `app` user (UID 1654) by default.
USER app
WORKDIR /app

COPY --from=build --chown=app:app /app/publish .

EXPOSE 8080

HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:8080/api/health || exit 1

ENTRYPOINT ["dotnet", "Sothema.Compliance.Api.dll"]
