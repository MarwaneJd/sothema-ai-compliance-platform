# Project Status — Sothema AI Compliance Platform

> **As of:** 2026-06-04
> **Current branch:** `main`
> **Last commit:** `117852d` — Reduce Fast-mode retrieval to top_k=6 (Deep Analysis keeps 10)
> **All previous untracked files now committed.**

---

## TL;DR

The platform is **functionally end-to-end and production-ready** in all
five layers — React frontend, ASP.NET Core API, Python AI service,
SQL Server, FAISS/BM25. Real Microsoft Entra ID auth is wired
end-to-end (MSAL frontend + JWT backend + DB-backed role resolution),
EF Core migrations replace the dev `EnsureCreated()` bootstrap, and
the SharePoint sync subsystem (webhooks + delta polling) is activated
and working.

The most recent batch of work (commits `117852d`–`14c3004`, 2026-06-02)
covers five focused improvements:

1. **Fast-mode top_k=6** (`117852d`) — Fast mode retrieves 6 chunks
   (down from 10) for tighter, less noisy context and lower latency;
   Deep Analysis keeps 10 for multi-hop coverage.
2. **Delta-sync correctness fix** (`0c6140c`) — Fixed a destructive loop
   where each cycle re-classified the same items as Modified, deleting
   segments without re-indexing. Three fixes: (a) `ContentHash` field on
   `Document` (quickXorHash/cTag/eTag) lets `ClassifyChange` skip
   unchanged items; (b) delta token persists in its own transaction
   (`PersistDeltaTokenAsync`) so it advances regardless of item failures;
   (c) each item dispatched in its own DI scope to prevent cross-item
   change-tracker pollution.
3. **Cross-encoder relevance surfaced** (`aa1a5c6`) — `relevance_score`
   in search results now uses the cross-encoder sigmoid score instead
   of raw RRF (which was bounded ~5–7% and looked uniformly low).
   Falls back to RRF when reranker is absent.
4. **Document delete fix** (`2d7f132`) — Deleting a document whose
   segments appeared in audit rows raised HTTP 500. `delete_by_document_id`
   now removes dependent `AiRequestSegments` first, then bulk-deletes
   segments via Core SQL, bypassing ORM cascade.
5. **DOCX table + header/footer extraction** (`14c3004`) — `_extract_docx`
   now walks paragraphs and tables interleaved (order preserved), renders
   table cells as pipe-joined rows, and pulls deduplicated header/footer
   text so tabular regulatory content is fully indexed.

Prior major work (commit `c442300`, 2026-05-11) added the full agentic
RAG Deep Analysis mode. Commit `6db6517` (2026-05-02) improved French
RAG retrieval quality with a multilingual BM25 tokenizer and eval harness.

The remaining gap before deployable production is **CI/CD pipelines
and cloud infrastructure** (`infrastructure/` directory still empty,
no GitHub Actions). Everything else is in place.

---

## 1 — Layer-by-Layer Status

### 1.1 Frontend — React / TypeScript / Vite

| Area | State | Notes |
|---|---|---|
| Project scaffold | ✅ Done | Vite + React + TypeScript + TailwindCSS, ESLint, Dockerfile, nginx.conf |
| Layout & routing | ✅ Done | `AppLayout`, `Sidebar`, `TopBar`, `RoleGuard`, React Router |
| Pages | ✅ Done | Dashboard, Documents, DocumentDetail, ComplianceAnalyses, ComplianceDetail, Chat, AuditLogs, Settings, Login, NotFound |
| UI component library | ✅ Done | `Button`, `Card`, `Badge`, `ScoreBadge`, `DataTable`, `Pagination`, `Modal`, `SearchInput`, `LoadingSpinner`, `EmptyState` |
| Charts | ✅ Done | `ScoreDistributionChart`, `CategoryBreakdownChart` (Recharts) |
| Type definitions | ✅ Done | `Document`, `ComplianceAnalysis`, `User`, `AuditLog`, `Chat`, etc. |
| Mock data layer | ✅ Done | Full mock data; toggled via `VITE_USE_MOCK` env var |
| Service layer — Documents / Compliance / Chat / Auth / Audit | ✅ Done | All wired to real API when `VITE_USE_MOCK=false` |
| Authentication — MSAL / Entra ID | ✅ **Done** | `@azure/msal-browser` + `@azure/msal-react` wired in `AuthContext.tsx`; `Login.tsx` page with pop-up/redirect flow; `MsalProvider` wraps the app in `main.tsx`; sign-out button in `TopBar` and `Settings` |
| Build artefact | ✅ Done | `dist/` deployable |
| Docker | ✅ Done | Multi-stage Nginx Dockerfile; port 3000 in compose |

### 1.2 Backend — ASP.NET Core 8 / Clean Architecture

| Area | State | Notes |
|---|---|---|
| Solution structure | ✅ Done | 4-project Clean Architecture: Domain, Application, Infrastructure, Api + Tests |
| Domain entities | ✅ Done | `Document`, `TextSegment`, `ComplianceAnalysis`, `AuditLog`, `User`, `Agent`, `UserQuery`, `AiRequest`, `AiRequestSegment`, `SharePointSyncState` (10 entities) |
| Repository interfaces + implementations | ✅ Done | All 10 entities covered; `RepositoryBase<T>` shared; EF Core SQL Server |
| `ComplianceDbContext` | ✅ Done | All entities registered; EF Fluent API configurations |
| Application — CQRS (MediatR) | ✅ Done | `IngestDocumentCommand`, `RemoveDocumentCommand`, `RequestAnalysisCommand`, `GetDocumentsQuery`, `GetDocumentByIdQuery`, `SearchDocumentsQuery`, `GetDocumentContentQuery`, `GetAnalysisQuery`, `GetAllAnalysesQuery`, `GetAnalysisByIdQuery`, `GetAuditLogsQuery` |
| Application — Behaviors | ✅ Done | `ValidationBehavior` (FluentValidation), `AuditBehavior` (auto-logs every command) |
| Application — Interfaces | ✅ Done | `ISharePointService`, `IAiService` (with `IngestDocumentAsync`/`RemoveDocumentAsync`), `ICurrentUserService`, `ISyncProcessor` |
| Infrastructure — `AiServiceClient` | ✅ Done | Typed `HttpClient`: `RequestAnalysisAsync`, `GetAnalysisStatusAsync`, `SearchAsync`, `IngestDocumentAsync`, `RemoveDocumentAsync` |
| Infrastructure — `SharePointService` (OBO/delegated) | ✅ Done | Real Microsoft Graph SDK implementation; user-context flows (search, manual ingest) |
| Infrastructure — `AppGraphClient` (app-only) | ✅ **Done** | `Azure.Identity.ClientSecretCredential`-backed singleton; used by background sync services that have no user context |
| Infrastructure — `StubSharePointService` | ✅ Done | Dev-mode stub; persists uploaded file bytes in `data/dev-files/` for re-analysis |
| Infrastructure — SharePoint Sync | ✅ **Activated and working** | `SharePointSyncProcessor`, `DeltaSyncService`, `SubscriptionRenewalService`, `WebhookController`. Hybrid webhook + delta-polling. Gated by `SharePointSync:Enabled`. `Document.ContentHash` (quickXorHash/cTag/eTag) deduplicates unchanged items; delta token commits in own transaction. |
| Authentication — JWT bearer + Entra ID | ✅ **Done** | `Microsoft.Identity.Web` validates real Entra-issued JWTs against `https://login.microsoftonline.com/{TenantId}/v2.0`; audience = `api://{ClientId}`. DevAuth scheme remains for local development. |
| Authentication — Role resolution | ✅ Done | `DatabaseRoleClaimsTransformation` resolves roles from the local `Users` table on first login (auto-creates user with `Authorization:DefaultNewUserRole`); short-circuits if the JWT already carries `ClaimTypes.Role` |
| API — Controllers | ✅ Done | `DocumentsController`, `ComplianceController`, `SearchController`, `AuditController`, `UsersController`, `HealthController`, `DevController`, `WebhookController` (anonymous, validates `clientState`) |
| API — `DevController` | ✅ Done (Development only) | `POST /api/dev/ingest` (multipart upload), `POST /api/dev/seed` |
| API — Authorization policies | ✅ Done | `RequireAdmin`, `RequireAnalyst`, default authenticated |
| Swagger / OpenAPI | ✅ Done | Available at `/swagger` in Development |
| Logging | ✅ Done | Serilog structured logging — console + rolling file; `CorrelationIdMiddleware` for distributed tracing |
| Docker | ✅ Done | Multi-stage Dockerfile; wired in compose |
| EF Core migrations | ✅ **Done** | `Infrastructure/Migrations/` populated; replaces `EnsureCreated()` for safe schema evolution in staging/production |

### 1.3 AI Service — Python / FastAPI

| Area | State | Notes |
|---|---|---|
| Project scaffold | ✅ Done | FastAPI, pydantic-settings, structlog, Dockerfile, requirements.txt |
| Configuration | ✅ Done | `AI_SERVICE_` prefix; multi-provider LLM support wired via env |
| Security | ✅ Done | `X-API-Key` header validation on all routes except `/api/health` |
| Database (SQLAlchemy) | ✅ Done | Async `mssql+aioodbc` engine; all 10 ORM models with PascalCase columns; full async repositories |
| Document processor | ✅ Done | PDF (pypdf), DOCX (python-docx), XLSX (openpyxl), PPTX (python-pptx), TXT/MD |
| Chunking | ✅ **Improved (2026-05-02)** | New `RegulatoryChunker` detects `Chapitre`/`Article`/numbered (`N.N.N`)/ALL-CAPS headings; uses `pysbd` for French sentence segmentation (handles `Cf. Art.`, `n° 12`, decimals). Each chunk gets a section breadcrumb prepended at index time (e.g. `SOP-001 › Chapitre 1 › Article 4 › 4.2.1`) — embedded by FAISS and indexed by BM25 so section context is searchable for free. Falls back to `TextChunker` for unstructured text. |
| Embedding | ✅ Done | `paraphrase-multilingual-MiniLM-L12-v2` (384 dims, multilingual incl. French/Arabic, L2-normalized). Loaded at startup. Set via `AI_SERVICE_EMBEDDING_MODEL_NAME` env override; `config.py` default still says `all-MiniLM-L6-v2` but actual deployment is multilingual. |
| FAISS vector store | ✅ Done | `IndexFlatIP` with positional ID map (`_pos_to_vs_id`), bidirectional lookup, disk persistence |
| BM25 keyword store | ✅ **Improved (2026-05-02)** | Multilingual-aware tokenizer: NFC casefold, per-token script detection, French Snowball stemming (`PyStemmer`), Arabic tashkeel stripping (`PyArabic`), French stopwords with negations preserved (`non`, `pas`, `aucun`). Index pickle carries `BM25_INDEX_VERSION` so on-disk indexes auto-rebuild when tokenization logic changes. |
| Hybrid retriever | ✅ Done | Reciprocal Rank Fusion (k=60) combining vector + BM25 ranks |
| RAG pipeline | ✅ Done | Embed query → hybrid retrieve → fetch segments → build prompt → LLM → answer |
| LLM providers | ✅ Done | Azure OpenAI, Groq (llama-3.3-70b), Ollama (local) — switched via `AI_SERVICE_LLM_PROVIDER` |
| Multi-agent graph (LangGraph) | ✅ Done | Supervisor + 6 specialized agents: DocumentRetrieval, ContentAnalysis, RegulatoryCompliance, ComplianceScoring, Explanation, Audit |
| Agentic RAG (Deep Analysis) | ✅ **Hardened (2026-05-14)** | `/api/agentic-search` with plan-aware complexity routing (single_pass vs multi_pass), synthesis-mode generate prompt for comparative queries, tenacity-wrapped verify with `-1.0` sentinel on rate limits, frontend "Not verified" UX. End-to-end measured 6–11s on paid Groq. |
| Fast-mode top_k | ✅ **Tuned (2026-06-02)** | Fast mode sends `top_k=6` (down from 10) for tighter context; Deep Analysis keeps `top_k=10`. |
| Relevance score | ✅ **Improved (2026-06-02)** | `relevance_score` in search API now uses sigmoid(cross-encoder logit) when reranker ran, RRF fallback otherwise. |
| DOCX extraction | ✅ **Improved (2026-06-02)** | Tables (pipe-joined rows) + header/footer text extracted by `_extract_docx`. |
| API endpoints | ✅ Done | `POST /api/documents/ingest`, `DELETE /api/documents/{id}`, `GET /api/documents/{id}/status`, `POST /api/search` (with `vector_store_id` populated in results), `POST /api/agentic-search` (Deep Analysis), `POST /api/analyze`, `GET /api/analyze/{jobId}/status`, `GET /api/health` |
| Agentic RAG — Deep Analysis | ✅ **Shipped (c442300 + untracked)** | `app/agents/agentic_rag/`: 6-node LangGraph (plan/retrieve/reflect/refine_query/generate/verify). `AgentBudget` (max 2 iter, 8 LLM calls, 25s). Plan-aware routing: single_pass vs multi_pass. GENERATE_SYSTEM_SYNTHESIS for comparative. tenacity verify (3×). Groundedness sentinel -1.0. `POST /api/agentic-search`. |
| Eval harness | ✅ **New (2026-05-02)** | `app/evals/`: strict JSONL goldset loader, `ranx`-backed retrieval metrics (recall@k, MRR, nDCG), thin LLM-as-judge for faithfulness and answer-relevance, interactive bootstrap CLI for labeling. Goldset file is empty until curated. |
| Operational tooling | ✅ **New (2026-05-02)** | `scripts/reset_indexes.py` (wipe FAISS + BM25), `scripts/ingest_local_files.py` (batch-ingest local files, bypasses .NET DevController, auto-rolls-back orphan rows on AI failure), `scripts/run_eval.py` (run goldset eval against local indexes) |
| Tests | ✅ Done | 97 unit tests passing — chunking, BM25 tokenization (French + Arabic + version migration), hybrid retriever, agents, eval harness, ingest script. Plus 11 pre-existing `test_api.py` errors caused by an unrelated `langgraph 0.2.0`/`langchain-openai 0.2.0` dependency conflict. |
| Docker | ✅ Done | Python 3.12-slim, ODBC Driver 18 install, FAISS volume mounted |
| Answer generation in search | ✅ Done | `/api/search` returns both ranked chunks and an LLM-generated `answer` field used by the Chat UI |

### 1.4 Data Storage

| Area | State | Notes |
|---|---|---|
| SQL Server | ✅ Done | Docker image `2022-latest`; `platform: linux/amd64` for Apple Silicon; persistent volume |
| Schema | ✅ Done | All 10 tables created via EF Core migrations on first deploy |
| FAISS index | ✅ Done | Persisted to Docker volume `faiss-data:/app/data/faiss_indexes` |
| BM25 index | ✅ Done | Co-located with FAISS index as `bm25_index.pkl`; version-tagged for safe upgrades |
| EF Core migrations | ✅ **Done** | `Infrastructure/Migrations/` populated; `dotnet ef database update` for staging/prod |

### 1.5 Infrastructure / DevOps

| Area | State | Notes |
|---|---|---|
| Docker Compose | ✅ Done | All 4 services: `sqlserver`, `backend-api`, `ai-service`, `frontend-web` |
| Environment file | ✅ Done | `.env.example` documented; `.env` present (gitignored) |
| CI/CD | ❌ **Not started** | No GitHub Actions yet — see Priority 1 below |
| Cloud infrastructure | ❌ **Not started** | `infrastructure/` directory empty (`.gitkeep` only) — see Priority 1 below |

---

## 2 — Integration Points — Current State

```
Browser (React + MSAL)
    │  ← Real Entra ID JWT (or VITE_USE_MOCK for dev)
    ▼
ASP.NET Core API :5136 (local) / :5000 (Docker)
    │  ← JwtBearer validation (Microsoft.Identity.Web)
    │  ← DatabaseRoleClaimsTransformation (DB-backed roles)
    │  ← ComplianceDbContext → SQL Server :1433
    │  ← AiServiceClient → AI Service :8000
    │  ← SharePointService (OBO/delegated, user-context)
    │  ← AppGraphClient (app-only, background sync)
    │  ← BackgroundServices: DeltaSyncService, SubscriptionRenewalService
    ▼
Python FastAPI :8000
    │  ← X-API-Key header
    │  ← FAISS + BM25 (local volume, multilingual-aware)
    │  ← SQLAlchemy → SQL Server :1433 (shared DB)
    │  ← LLM: Groq / Azure OpenAI / Ollama (env-selectable)
    ▼
SQL Server :1433
    ↑
SharePoint (Microsoft Graph)
  webhook ──▶ WebhookController (Sothema → SharePoint also via Graph)
  delta poll ──▶ DeltaSyncService (every 20 min default)
```

---

## 3 — What Needs to Be Done Next

### Priority 1 — CI/CD and Cloud Infrastructure (the only remaining production gap)

| Task | Layer | Description |
|---|---|---|
| **GitHub Actions pipeline** | DevOps | `dotnet build` + `dotnet test` on every PR; `pytest` on AI service; Docker build verification |
| **Azure Container Apps / App Service deployment** | Infrastructure | Populate the empty `infrastructure/` directory with Bicep or Terraform for: SQL Server (Azure SQL), backend API, AI service, frontend (Static Web App or Container App), Key Vault for secrets |
| **Key Vault integration** | Backend + AI Service | Move `AzureAd:ClientSecret`, `AiService:ApiKey`, `SharePointSync:WebhookClientState`, `SA_PASSWORD` into Azure Key Vault; reference via managed identity |
| **Application Insights / monitoring** | Backend + AI Service | Add Serilog Application Insights sink to the .NET backend; structured logging already in place; add OpenTelemetry traces for RAG pipeline latency |

### Priority 2 — Production Hardening

| Task | Layer | Description |
|---|---|---|
| **Resolve `langgraph 0.2.0` ↔ `langchain-openai 0.2.0` dep conflict** | AI Service | Pre-existing pin conflict prevents `pip install -r requirements.txt --strict` and breaks `app.main` imports in `tests/test_api.py` (11 errors). Likely fix: bump `langgraph` to ≥0.2.20 which allows `langchain-core>=0.3`. |
| **Transactional segment deletion** | Backend | `RemoveDocumentCommandHandler` deletes `TextSegments` one-by-one through the repository. Refactor to a single `ExecuteDeleteAsync` / raw SQL for large documents to avoid N+1 round-trips. |
| **FAISS index persistence under concurrent writes** | AI Service | FAISS is saved synchronously after every ingest/remove. Under concurrent requests this can corrupt the file. Wrap saves in a per-process `asyncio.Lock`. |
| **Remove `DevController`** | Backend | `DevController` is tagged for removal before production. Already protected by `_env.IsDevelopment()` check, but should be excluded from production build entirely. |
| **CORS lockdown** | AI Service | AI service currently uses `allow_origins=["*"]` — tighten to the backend API's internal Docker hostname only. |
| **`WebhookClientState` secret rotation** | Backend | Document the process for rotating `SharePointSync:WebhookClientState` in production (requires re-creating the Graph subscription). |

### Priority 3 — Testing Gaps

| Task | Layer | Description |
|---|---|---|
| **Backend unit tests** | Tests | `Sothema.Compliance.Tests` exists but contains no test files. Add handler tests for `IngestDocumentCommand`, `RemoveDocumentCommand`, `RequestAnalysisCommand`, and the sync processor (`SharePointSyncProcessor.ClassifyChange` is a pure static method — easy to unit test) |
| **Integration tests** | Tests | `WebApplicationFactory`-based tests for `DocumentsController`, `ComplianceController`, `WebhookController` (validation handshake + `clientState` rejection) |
| **AI service `test_api.py`** | AI Service | 11 errors block this test file; resolves with the langgraph dep conflict fix above |

### Priority 4 — RAG Quality Tuning (deferred until real query logs exist)

The 2026-05-02 RAG commit added the eval harness and two default-on
improvements (BM25 + chunker). Further tuning (cross-encoder reranker,
MMR/dedup, query planner with HyDE) is intentionally not implemented —
it's premature without:

1. A curated goldset of ≥30 real French regulatory queries.
2. Real user query logs that surface specific failure modes.

When ready: bootstrap a goldset via `python -m app.evals.bootstrap`,
run `python -m scripts.run_eval`, and revisit. The original
architectural plan (cross-encoder reranker, MMR, intent prompts,
faithfulness check) lives in `/Users/mac/.claude/plans/` if needed
later.

---

## 4 — Known Issues / Technical Debt

| Issue | Severity | Location |
|---|---|---|
| `langgraph 0.2.0` ↔ `langchain-openai 0.2.0` pin conflict | Medium | `ai-service-python/requirements.txt:9-11` — blocks `--strict` reinstalls and `test_api.py` |
| `IngestDocumentCommand` calls `RequestAnalysisAsync` (full LLM pipeline) rather than `IngestDocumentAsync` (index only) — ambiguous separation of ingestion vs. analysis | Medium | `Application/Features/Documents/Commands/IngestDocumentCommand.cs:84` |
| `RemoveDocumentCommand` deletes segments in a loop (N round-trips to DB) | Low | `Application/Features/Documents/Commands/RemoveDocumentCommand.cs:56–59` |
| AI service CORS allows `*` — should be restricted to backend container | Low | `ai-service-python/app/main.py:34` |
| `DevController` (remove before prod) | Low | `Api/Controllers/DevController.cs` |
| `infrastructure/` directory is empty | Info | `infrastructure/.gitkeep` |
| `config.py` embedding model default (`all-MiniLM-L6-v2`) does not match deployed model (`paraphrase-multilingual-MiniLM-L12-v2`) — env override is intentional but the default looks wrong at first glance | Info | `ai-service-python/app/config.py:36` |

---

## 5 — Quick Start (Current Dev Setup)

```bash
# 1. Copy env
cp docker/.env.example docker/.env
# Edit docker/.env: set SA_PASSWORD, AI_SERVICE_API_KEY, LLM_PROVIDER + matching key,
# Entra ID TenantId/ClientId/ClientSecret, SharePoint SiteId/DriveId

# 2. Start all services
docker compose -f docker/docker-compose.yml up --build

# 3. Access
#   Frontend:    http://localhost:3000
#   Backend API: http://localhost:5000/swagger
#   AI Service:  http://localhost:8000/docs
#   SQL Server:  localhost:1433

# 4. Ingest a test document (no SharePoint needed) — DevController route
curl -X POST http://localhost:5000/api/dev/ingest \
  -H "Authorization: Bearer dev" \
  -F "file=@/path/to/SOP.pdf"

# 4b. OR batch-ingest a folder of files via the AI service directly
cd ai-service-python
source .venv/bin/activate
python -m scripts.ingest_local_files --dir /path/to/sops --apply

# 5. Search / chat
# Use the Chat page in the UI, or:
curl -X POST http://localhost:8000/api/search \
  -H "X-API-Key: <AI_SERVICE_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"query": "Quelle est la procédure de contrôle qualité ?", "top_k": 5}'
```

---

## 6 — File Inventory Summary

| Component | Location | Status |
|---|---|---|
| React frontend | `frontend-web/` | ✅ Complete with real MSAL auth |
| ASP.NET Core API | `backend-dotnet-api/` | ✅ Complete with real Entra ID + SharePoint sync |
| Python AI service | `ai-service-python/` | ✅ Complete with multilingual French RAG + eval harness |
| Docker Compose | `docker/docker-compose.yml` | ✅ Complete |
| Cloud infrastructure | `infrastructure/` | ❌ Empty |
| CI/CD | `.github/` (absent) | ❌ Not started |
| Documentation | `docs/` | ✅ Architecture, context, implementation plans, this status doc, technology changelog, sync subsystem design, credentials guide, report (LaTeX), **PlantUML diagram sources** (`docs/report/diagrams/*.puml`) |
