# Docker Implementation Plan — Sothema AI Compliance Platform

> **As of:** 2026-05-04
> **Goal:** Bring the four existing Docker files (3 service Dockerfiles +
> `docker-compose.yml`) from "functional in dev" to "production-ready
> containers", so the platform can be reliably spun up via
> `docker compose up --build` and later promoted to cloud (Azure
> Container Apps / equivalent).
> **Status:** planning — no edits made yet.

---

## 1. Context

The platform's four Docker files all exist and work for the current
"single developer on Apple M3" scenario. They are:

- [frontend-web/Dockerfile](frontend-web/Dockerfile) — multi-stage Node→Nginx, ~13 lines
- [ai-service-python/Dockerfile](ai-service-python/Dockerfile) — single-stage Python 3.12-slim with ODBC Driver 18, ~30 lines
- [backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile](backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile) — multi-stage SDK→ASP.NET runtime, ~13 lines
- [docker/docker-compose.yml](docker/docker-compose.yml) — 4-service compose with shared `.env`

They were written quickly during scaffolding and have not been revisited.
Each one carries straightforward gaps that, individually, are minor — but
collectively block:

- **Reliable cold start** (no healthchecks → backend boots before SQL Server is ready)
- **Reasonable image size** (AI service single-stage ships build tools to prod)
- **Layer caching** (backend's `COPY . .` before `dotnet restore` invalidates the restore layer on every source change)
- **Security baseline** (every service runs as root)
- **Cloud portability** (frontend env vars baked at build time with no `ARG`s)

This plan addresses those gaps without changing the deployment topology
or service contracts. No new services, no new languages, no new orchestrator —
just the same 4 services, packaged better.

---

## 2. Current state — file-by-file audit

### 2.1 [frontend-web/Dockerfile](frontend-web/Dockerfile)

| What's there | What's missing |
|---|---|
| Multi-stage Node→Nginx (good) | No `.dockerignore` — `node_modules`, `dist`, `.git` enter build context |
| `npm ci` runs before `COPY . .` (good for caching deps) | No non-root user (Nginx runs as root) |
| `EXPOSE 80`, default Nginx CMD | No healthcheck — Compose can't gate startup on it |
| | No build-time `ARG`s for `VITE_USE_MOCK`, API URLs (env vars are baked into the bundle at build, so these are needed for deployment-time config) |

### 2.2 [ai-service-python/Dockerfile](ai-service-python/Dockerfile)

| What's there | What's missing |
|---|---|
| ODBC Driver 18 install with EULA accepted (correct) | **Single-stage** — final image ships build tools (`build-essential`, `gnupg2`, `unixodbc-dev` headers). Probably ~1.5 GB when it could be ~600 MB |
| `apt-get purge --auto-remove` for some build tools (partial cleanup) | Runs as root |
| `requirements.txt` copied before source (good for caching) | No healthcheck — uvicorn readiness is invisible to Compose |
| `EXPOSE 8000` | Embedding model (`paraphrase-multilingual-MiniLM-L12-v2`, ~80 MB) downloads from HuggingFace at startup. Cold start in cloud is slow and depends on HF being reachable |
| | Missing `PYTHONUNBUFFERED=1`, `PYTHONDONTWRITEBYTECODE=1` (logs buffered, .pyc files cluttering image) |
| | No `.dockerignore` — `.venv/`, `__pycache__/`, `data/`, `.pytest_cache/` enter build context |
| | No init system — uvicorn's signal handling (SIGTERM during graceful shutdown) may not propagate cleanly |

### 2.3 [backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile](backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile)

| What's there | What's missing |
|---|---|
| Multi-stage SDK→ASP.NET runtime (good) | `COPY . .` happens **before** `dotnet restore` — every source change busts the restore cache. Should be: copy `*.csproj` + `*.sln`, restore, then copy source. |
| `dotnet publish -c Release` (correct) | Runs as root |
| `EXPOSE 8080` | No healthcheck |
| | Uses full `aspnet:8.0` runtime (~210 MB). Alternatives: `aspnet:8.0-alpine` (~110 MB) or `aspnet:8.0-jammy-chiseled` (~100 MB, distroless) |
| | No `.dockerignore` — `bin/`, `obj/`, `.vs/`, `.git/`, `*.user` enter build context |

### 2.4 [docker/docker-compose.yml](docker/docker-compose.yml)

| What's there | What's missing |
|---|---|
| All 4 services declared (`sqlserver`, `backend-api`, `ai-service`, `frontend-web`) | **No healthchecks on any service** — `depends_on` is bare, so backend starts before SQL Server is ready |
| Volumes for SQL Server data (`sqlserver-data`) and FAISS (`faiss-data`) | `depends_on` should switch to `condition: service_healthy` once healthchecks exist |
| `${SA_PASSWORD}`, `${AI_SERVICE_API_KEY}` from env | Need to verify `docker/.env.example` exists and lists every variable referenced |
| `platform: linux/amd64` on SQL Server (Apple Silicon Rosetta) | Frontend Nginx serves on port 80 mapped to 3000 — fine for local but no SSL termination configured |
| `depends_on` declarations exist | No `restart: unless-stopped` on long-running services |

---

## 3. Implementation plan

Four phases, ordered so each is independently revertible. Estimated
~3 hours total for a focused session.

### Phase A — `.dockerignore` files (~20 min)

Smallest, highest-leverage change. Add one `.dockerignore` per service
directory. Each should mirror the project's existing `.gitignore` plus
local-development artefacts that should never enter a container build.

**Files to create:**

- `frontend-web/.dockerignore`
  ```
  node_modules
  dist
  .git
  .gitignore
  .env
  .env.local
  *.log
  .DS_Store
  README.md
  Dockerfile
  ```

- `ai-service-python/.dockerignore`
  ```
  .venv
  __pycache__
  *.pyc
  *.pyo
  .pytest_cache
  .ruff_cache
  .mypy_cache
  data/
  .git
  .gitignore
  .env
  .env.local
  *.log
  .DS_Store
  README.md
  Dockerfile
  tests/
  ```
  > Note: `tests/` is excluded so the production image stays slim. If
  > you want the ability to `docker exec` into a container and run
  > tests, leave `tests/` out of the ignore list — but then also keep
  > `pytest` in the production deps, which we don't.

- `backend-dotnet-api/.dockerignore`
  ```
  **/bin/
  **/obj/
  **/.vs/
  **/.user
  .git
  .gitignore
  *.log
  .DS_Store
  README.md
  **/Dockerfile
  ```

**Why first:** these are pure additions. They reduce build-context size
(faster `docker build`, fewer surprises in production images) and don't
risk breaking anything. Even if Phases B–D get reverted, these are
worth keeping.

### Phase B — Dockerfile rewrites (~90 min)

#### B.1 — `ai-service-python/Dockerfile` (biggest gain)

Switch to multi-stage, drop build tools from the runtime image, run as
non-root, add healthcheck, optionally pre-bake the embedding model.

```dockerfile
# ───────────────────────────────────────────────────
# Stage 1: build (compile wheels, install ODBC sources)
# ───────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build deps for any wheels that need to compile (PyStemmer, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        gnupg2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ───────────────────────────────────────────────────
# Stage 2: runtime (slim, ODBC driver only, no build tools)
# ───────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH=/home/app/.local/bin:$PATH

# Install ODBC driver (runtime only — no -dev packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl \
        gnupg2 \
        ca-certificates \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
       | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list \
       > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && apt-get purge -y --auto-remove curl gnupg2 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd --create-home --uid 1001 app
USER app
WORKDIR /home/app

# Copy installed Python packages from builder
COPY --from=builder --chown=app:app /root/.local /home/app/.local

# Copy app code (last so source changes don't bust deps cache)
COPY --chown=app:app . .

# Pre-bake embedding model to avoid HuggingFace download on first start
# (decision pending — see §4.2 below)
# RUN python -c "from sentence_transformers import SentenceTransformer; \
#     SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')"

RUN mkdir -p data/faiss_indexes

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Expected result:** image size ~600 MB (was ~1.5 GB), startup model
download eliminated if pre-bake is enabled, signal handling is clean
(uvicorn as PID 1 is fine when the host is Linux).

#### B.2 — `backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile`

Fix layer caching (restore before source copy), use a smaller runtime
base, run as non-root, add healthcheck.

```dockerfile
# ───────────────────────────────────────────────────
# Stage 1: build
# ───────────────────────────────────────────────────
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /src

# Copy only project files first for layer-cached restore
COPY *.sln .
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

# Non-root user
RUN addgroup -S app && adduser -S app -G app
USER app
WORKDIR /app

COPY --from=build --chown=app:app /app/publish .

EXPOSE 8080

# Curl is in alpine by default — use the platform health endpoint
HEALTHCHECK --interval=10s --timeout=3s --start-period=20s --retries=3 \
    CMD wget -qO- http://localhost:8080/api/health || exit 1

ENTRYPOINT ["dotnet", "Sothema.Compliance.Api.dll"]
```

**Expected result:** image size ~110 MB (was ~210 MB), `dotnet restore`
cached across source-only changes, container fails health if the API
isn't responding.

> **Note on `wget` in alpine:** `aspnet:8.0-alpine` includes `wget` by
> default. If a future base image strips it, switch the healthcheck to
> a managed health endpoint check via `dotnet` itself, or add
> `apk add --no-cache curl`.

#### B.3 — `frontend-web/Dockerfile`

Add build args for env, non-root Nginx, healthcheck.

```dockerfile
# ───────────────────────────────────────────────────
# Stage 1: build the SPA bundle
# ───────────────────────────────────────────────────
FROM node:20-alpine AS build
WORKDIR /app

# Build-time env (Vite bakes these into the bundle)
ARG VITE_USE_MOCK=false
ARG VITE_API_BASE_URL=http://localhost:5000
ARG VITE_AZURE_AD_CLIENT_ID=
ARG VITE_AZURE_AD_TENANT_ID=
ARG VITE_AZURE_AD_REDIRECT_URI=
ENV VITE_USE_MOCK=$VITE_USE_MOCK \
    VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_AZURE_AD_CLIENT_ID=$VITE_AZURE_AD_CLIENT_ID \
    VITE_AZURE_AD_TENANT_ID=$VITE_AZURE_AD_TENANT_ID \
    VITE_AZURE_AD_REDIRECT_URI=$VITE_AZURE_AD_REDIRECT_URI

COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# ───────────────────────────────────────────────────
# Stage 2: serve with Nginx (non-root)
# ───────────────────────────────────────────────────
FROM nginx:alpine AS runtime

# nginx:alpine ships an `nginx` user already; switch to it.
# /var/cache/nginx and /var/run need to be writable by that user.
RUN chown -R nginx:nginx /var/cache/nginx /var/run \
 && touch /var/run/nginx.pid \
 && chown nginx:nginx /var/run/nginx.pid

COPY --from=build --chown=nginx:nginx /app/dist /usr/share/nginx/html
COPY --chown=nginx:nginx nginx.conf /etc/nginx/conf.d/default.conf

# Listen on a non-privileged port so non-root works without setcap
# (the existing nginx.conf may need its `listen 80;` updated to
# `listen 8080;` — verify before applying)
EXPOSE 8080

USER nginx

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:8080/ || exit 1

CMD ["nginx", "-g", "daemon off;"]
```

> **Action item:** verify and update `frontend-web/nginx.conf` to listen
> on `8080` instead of `80` if it doesn't already. Update the Compose
> port mapping to `"3000:8080"` accordingly.

### Phase C — `docker-compose.yml` updates (~30 min)

Add healthchecks to every service, switch `depends_on` to
`condition: service_healthy`, verify env file completeness, add
`restart: unless-stopped`.

```yaml
services:
  sqlserver:
    image: mcr.microsoft.com/mssql/server:2022-latest
    platform: linux/amd64
    environment:
      ACCEPT_EULA: "Y"
      SA_PASSWORD: "${SA_PASSWORD}"
    ports:
      - "1433:1433"
    volumes:
      - sqlserver-data:/var/opt/mssql
    healthcheck:
      # SQL Server image ships sqlcmd at this path
      test: ["CMD-SHELL", "/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P \"$$SA_PASSWORD\" -No -Q 'SELECT 1' || exit 1"]
      interval: 10s
      timeout: 5s
      retries: 10
      start_period: 30s
    restart: unless-stopped

  ai-service:
    build:
      context: ../ai-service-python
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - AI_SERVICE_API_KEY=${AI_SERVICE_API_KEY}
      - AI_SERVICE_DATABASE_CONNECTION_STRING=mssql+aioodbc:///?odbc_connect=Driver={ODBC Driver 18 for SQL Server};Server=sqlserver,1433;Database=SothemaCompliance;UID=sa;PWD=${SA_PASSWORD};TrustServerCertificate=yes
      # ... existing env vars ...
    volumes:
      - faiss-data:/home/app/data/faiss_indexes
    depends_on:
      sqlserver:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health').read()"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 30s
    restart: unless-stopped

  backend-api:
    build:
      context: ../backend-dotnet-api
      dockerfile: src/Sothema.Compliance.Api/Dockerfile
    ports:
      - "5000:8080"
    environment:
      - ASPNETCORE_ENVIRONMENT=Development
      # ... existing env vars ...
    depends_on:
      sqlserver:
        condition: service_healthy
      ai-service:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/api/health"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 20s
    restart: unless-stopped

  frontend-web:
    build:
      context: ../frontend-web
      dockerfile: Dockerfile
      args:
        VITE_USE_MOCK: "false"
        VITE_API_BASE_URL: "http://localhost:5000"
        # Entra ID vars from .env so the bundle is built with real values
        VITE_AZURE_AD_CLIENT_ID: "${VITE_AZURE_AD_CLIENT_ID}"
        VITE_AZURE_AD_TENANT_ID: "${VITE_AZURE_AD_TENANT_ID}"
        VITE_AZURE_AD_REDIRECT_URI: "${VITE_AZURE_AD_REDIRECT_URI}"
    ports:
      - "3000:8080"
    depends_on:
      backend-api:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "wget", "-qO-", "http://localhost:8080/"]
      interval: 10s
      timeout: 3s
      retries: 3
      start_period: 5s
    restart: unless-stopped

volumes:
  sqlserver-data:
  faiss-data:
```

**Verify `docker/.env.example`:** must list every `${VAR}` referenced
in compose. Audit before applying. Probable missing entries:
`VITE_AZURE_AD_CLIENT_ID`, `VITE_AZURE_AD_TENANT_ID`,
`VITE_AZURE_AD_REDIRECT_URI`.

### Phase D — End-to-end verification (~30 min)

1. Stop and remove existing containers + volumes:
   ```bash
   cd docker
   docker compose down -v
   ```

2. Build and start with healthcheck gating:
   ```bash
   docker compose up --build
   ```
   Watch the logs — expected order:
   - `sqlserver` starts and becomes healthy (~30 s)
   - `ai-service` starts (waits for sqlserver), embedding model loads, becomes healthy (~10 s if pre-baked, ~30 s if not)
   - `backend-api` starts (waits for both), runs EF migrations, becomes healthy
   - `frontend-web` starts last

3. Verify healthchecks:
   ```bash
   docker compose ps
   # All services should show "healthy" in the STATUS column
   ```

4. Hit each `/health` endpoint:
   ```bash
   curl http://localhost:8000/api/health
   curl http://localhost:5000/api/health
   curl http://localhost:3000/
   ```

5. End-to-end smoke: ingest a test document via `POST /api/dev/ingest`
   and run a search query — same flow as
   `docs/project-status.md` §5.

6. Image size sanity check:
   ```bash
   docker images | grep sothema
   # ai-service should be < 800 MB (was ~1.5 GB)
   # backend-api should be < 200 MB (was ~280 MB)
   # frontend-web should be < 50 MB
   ```

---

## 4. Open decisions (need your input)

### 4.1 Backend runtime base image

| Option | Image size | Pros | Cons |
|---|---|---|---|
| `aspnet:8.0` (current) | ~210 MB | Familiar, full toolset | Largest |
| **`aspnet:8.0-alpine`** (recommended) | ~110 MB | Small, has `sh`/`wget`, debuggable | musl libc — rare compat issues with native-deps NuGets |
| `aspnet:8.0-jammy-chiseled` | ~100 MB | Microsoft's distroless, smallest secure baseline | No shell — can't `docker exec` for debugging, healthcheck must use embedded HTTP probe |

**Recommendation:** alpine. Small enough, debuggable, broad compatibility.
Switch to chiseled later when production observability is in place
(App Insights tracing covers what shell-debugging would).

### 4.2 Pre-bake the embedding model into the AI service image?

| Option | Image size | First-start latency | Notes |
|---|---|---|---|
| Pre-bake (recommended for prod) | +80 MB (~680 MB total) | Instant | Worth it for cloud — eliminates a runtime dependency on HuggingFace |
| Don't pre-bake | ~600 MB | +10 s on first container start | Smaller image; HF cache can be a mounted volume in dev |

**Recommendation:** pre-bake. The 80 MB is trivial against the cost of
a flaky HF download blocking a production container start. Dev iterations
already cache the model in the volume mount, so this only affects fresh
containers.

---

## 5. Out of scope (for this session)

Explicitly deferred to keep scope tight:

- **CI/CD GitHub Actions** — separate session. CI will pull these images
  once they're solid; doing CI first means rebuilding images-as-CI-pipelines
  later.
- **Cloud infrastructure (Bicep / Terraform)** — depends on choice of
  Azure Container Apps vs App Service vs AKS. The Dockerfiles improved
  here are deploy-target-agnostic, so this can wait.
- **Image signing, SBOM generation, Trivy / Snyk scans** — production
  polish, not blocking.
- **Distroless / chiseled migration** — see §4.1; defer until prod
  observability is in place.
- **Multi-arch builds** (`linux/arm64` for Apple Silicon native images) —
  would speed up local builds significantly but adds a `buildx` dependency.
  Defer.

---

## 6. Verification plan

Per phase, the acceptance criteria are:

| Phase | Acceptance |
|---|---|
| A | `docker build` for each service shows a smaller "transferring context" line; no behavioural change |
| B (AI service) | Image size < 800 MB; container runs as UID 1001; `docker inspect` shows healthcheck CMD |
| B (backend) | Source-only changes don't trigger `dotnet restore`; image size < 200 MB; healthcheck appears in `docker inspect` |
| B (frontend) | Bundle is built with the supplied `VITE_*` env; container runs as `nginx` user; healthcheck appears |
| C | `docker compose up` starts services in dependency order; `docker compose ps` shows all healthy after ~60 s |
| D | All four `/health` endpoints respond 200; ingest + search smoke test passes against the running stack |

---

## 7. Estimated total effort

~3 hours for a focused session, broken down:

- Phase A: 20 min
- Phase B: 90 min (AI service ~40, backend ~30, frontend ~20)
- Phase C: 30 min
- Phase D: 30 min (more if a healthcheck misbehaves and needs tuning)

If anything goes badly wrong, rollback is trivial — every change in
this plan is contained to Docker artefacts. `git checkout HEAD --
**/Dockerfile docker-compose.yml` reverts everything.

---

## 8. Files touched

| File | Action |
|---|---|
| `frontend-web/.dockerignore` | new |
| `ai-service-python/.dockerignore` | new |
| `backend-dotnet-api/.dockerignore` | new |
| `frontend-web/Dockerfile` | rewrite (multi-stage with ARGs, non-root, healthcheck) |
| `ai-service-python/Dockerfile` | rewrite (multi-stage, non-root, healthcheck, optional pre-bake) |
| `backend-dotnet-api/src/Sothema.Compliance.Api/Dockerfile` | rewrite (layer-cache restore, alpine runtime, non-root, healthcheck) |
| `frontend-web/nginx.conf` | edit (`listen 80` → `listen 8080`) |
| `docker/docker-compose.yml` | edit (healthchecks, `condition: service_healthy`, `restart`, frontend `args`, port mapping) |
| `docker/.env.example` | edit (add any missing `VITE_*` entries) |

No application code changes, no new dependencies, no schema changes.
