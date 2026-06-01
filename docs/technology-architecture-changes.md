# Technology & Architecture Changes — Sothema AI Compliance Platform

> **Period covered:** 2026-03-26 (initial commit) → 2026-05-02 (current)
> **Source:** git log + comparison against `docs/architecture.md` and the report's
> chapter 3 design snapshot.
> **Granularity:** changes that affect the *technology stack*, the *layered
> architecture*, the *runtime topology*, or the *security/identity model*.
> Pure code refactors and bug fixes are intentionally omitted.

---

## TL;DR

The platform was scaffolded on **2026-03-26** with the AI service (FastAPI +
LangGraph + RAG) effectively complete and the .NET side reduced to a skeleton
of Domain entities. Over five working weeks, three major waves brought the
backend to feature parity, then closed the production gap:

1. **Application layer wave** (2026-04-09): CQRS / MediatR / FluentValidation
   plumbing + a third LLM provider (Ollama).
2. **Infrastructure wave** (2026-04-16): Controllers, repositories, EF Core
   configurations, Serilog, middleware, `AiServiceClient`,
   `SharePointService` (delegated/OBO), `StubSharePointService` for dev.
3. **Production-readiness wave** (2026-04-21 → 2026-04-28, current
   uncommitted work): real Entra ID JWT validation, MSAL frontend login,
   DB-backed role resolution, **app-only Graph client** for background work,
   **SharePoint sync subsystem** (webhooks + delta polling), EF Core
   migrations, frontend sign-out.

Three deltas vs the original `docs/architecture.md`:

- The architecture is now **dual-identity** (delegated OBO *and* app-only
  client-credentials) instead of OBO-only.
- A **sync subsystem** was introduced — `architecture.md` only described
  on-demand SharePoint reads; the platform now maintains a continuously
  synchronised local index.
- **Role resolution** is now sourced from the local database via an
  `IClaimsTransformation`, not from Entra App Roles.

---

## 1. Commit-by-commit timeline

### Phase 0 — Initial scaffold (b26dea7, 2026-03-26)

**What landed:** the entire Python AI service in working state, plus a
.NET solution skeleton and a React frontend with mock data.

**Python side (already production-shaped):**

- FastAPI + pydantic-settings + structlog + Dockerfile.
- Document processor: PDF (pypdf), DOCX (python-docx), XLSX (openpyxl),
  PPTX (python-pptx), TXT/MD.
- Token-aware chunking (tiktoken, 512 tokens / 50 overlap).
- Local sentence-transformers embeddings (384 dims, L2-normalised). Default
  model in `config.py` is `all-MiniLM-L6-v2`; the actual deployment
  switched to `paraphrase-multilingual-MiniLM-L12-v2` via
  `AI_SERVICE_EMBEDDING_MODEL_NAME` to handle French/multilingual
  pharmaceutical documentation. Same vector dimension (384), so no FAISS
  re-indexing required.
- FAISS `IndexIDMap(IndexFlatIP)` with bidirectional id map and disk
  persistence.
- BM25 (`rank_bm25.BM25Okapi`) co-located with the FAISS index.
- Hybrid retriever with **Reciprocal Rank Fusion** (k=60).
- LangGraph multi-agent system: Supervisor + 6 agents (DocumentRetrieval,
  ContentAnalysis, RegulatoryCompliance, ComplianceScoring, Explanation,
  Audit).
- Two LLM providers: **Azure OpenAI** + **Groq** (llama-3.3-70b).
- API endpoints: `/api/documents/ingest`, `/api/search`, `/api/analyze`,
  `/api/analyze/{jobId}/status`, `/api/health`.
- API-key gate (`X-API-Key`).
- Async SQLAlchemy (`mssql+aioodbc`) with PascalCase columns to share the
  schema with EF Core.
- pytest suite (chunking, hybrid retriever, agents, API).

**.NET side (skeleton):**

- 4-project Clean Architecture: `Domain` / `Application` (empty) /
  `Infrastructure` (empty) / `Api` (default template).
- Domain entities: `Document`, `TextSegment`, `ComplianceAnalysis`,
  `AuditLog`, `User`, `Agent`, `UserQuery`, `AiRequest`, `AiRequestSegment`.
- Domain enums: `AnalysisStatus`, `UserRole`.
- Repository interfaces (no implementations).

**Frontend side:** Vite + React + TS + Tailwind, layout, routing, mock data
toggle (`VITE_USE_MOCK`).

**Docker Compose:** `sqlserver`, `backend-api`, `ai-service`, `frontend-web`.

### Phase 0.1 — Empty-folder placeholder (17188f4, 2026-03-26)

`infrastructure/.gitkeep` only. No technology change.

### Phase 1 — Application layer + Ollama (84dd886, 2026-04-09)

**Backend Application layer:**

- **MediatR** as the CQRS mediator.
- **FluentValidation** wired through a `ValidationBehavior<TRequest,
  TResponse>` pipeline.
- **`AuditBehavior`** that auto-writes an `AuditLogs` row after every
  `ICommand`.
- **AutoMapper** profiles (`MappingProfile`).
- DTO catalogue: `DocumentDto`, `ComplianceResultDto`, `AuditLogDto`,
  `SharePointSearchResultDto`, `UserProfileDto`.
- Commands: `IngestDocumentCommand`, `RequestAnalysisCommand`.
- Queries: `GetDocumentsQuery`, `GetDocumentByIdQuery`,
  `GetDocumentContentQuery`, `SearchDocumentsQuery`, `GetAnalysisQuery`,
  `GetAuditLogsQuery`.
- Cross-layer abstractions: `ISharePointService`, `IAiService`,
  `ICurrentUserService`.
- A `Result<T>` envelope (poor-man's `Either`) and a `PaginatedList<T>`.

**AI service:** added **Ollama** as a third LLM provider, switchable via
`AI_SERVICE_LLM_PROVIDER` — enables fully-local development without external
API keys.

### Phase 2 — Infrastructure layer (91b6777, 2026-04-16)

The big one: 71 files, +3 567 / -312.

**Controllers:** `DocumentsController`, `ComplianceController`,
`SearchController`, `AuditController`, `UsersController`, `HealthController`,
`DevController`.

**Middleware:**

- `CorrelationIdMiddleware` — propagates a request-correlation header
  through Serilog's `LogContext` for distributed tracing.
- `GlobalExceptionHandlerMiddleware` — uniform JSON error response.

**Persistence:**

- `ComplianceDbContext` registered with all entities.
- EF Core Fluent API configurations for each of the 9 entities.
- Repositories implementing each `I*Repository`, plus a generic
  `RepositoryBase<T>`.

**Services:**

- `AiServiceClient` (typed `HttpClient`) for `RequestAnalysisAsync`,
  `GetAnalysisStatusAsync`, `SearchAsync`.
- `SharePointService` (Microsoft Graph SDK, OBO/delegated) — production
  implementation behind the same `ISharePointService` interface.
- `StubSharePointService` — dev-mode fallback that persists uploaded
  bytes under `data/dev-files/` so that the analysis pipeline can be
  exercised without SharePoint.
- `CurrentUserService` reading claims from `HttpContext`.

**Logging:** **Serilog** added with console + rolling file sinks,
structured properties, `Microsoft.Extensions.Logging` bridging.

**Authentication scaffold:** `Microsoft.Identity.Web` packages added; JWT
bearer middleware configured; **DevAuth scheme** introduced for local
development (bypasses Entra ID, hardcodes a dev profile).

**AI service:** `analysis.py` extended to also call the RAG ingestion
pipeline, ensuring documents analysed from the backend become searchable
afterwards. SQL truncation bug under FreeTDS fixed by switching driver
parameters.

### Phase 2.1 — DevController upload-pipeline fix (b6a6fa0, 2026-04-16)

`DevController.cs` corrected so `POST /api/dev/ingest` actually persists
the file bytes the AI service later re-reads. Frontend `Documents.tsx`
calls aligned. No architecture change — just unblocking dev iteration.

### Phase 3 — Production-readiness wave (2026-04-21 → 2026-04-28)

This is the work currently on disk and not yet in `git log`. It closes
the gap to "first real Entra ID login + first real SharePoint document
indexed automatically".

**Frontend:**

- `frontend-web/src/auth/` package added — MSAL configuration
  (`msalConfig`, `loginRequest`).
- `Login.tsx` page with MSAL pop-up / redirect flow.
- `AuthContext.tsx` rewritten to consume MSAL tokens; stores ID token,
  surfaces user identity to the React tree.
- `main.tsx` wraps the app in `MsalProvider`.
- `TopBar` + `Settings` get a sign-out button; `Settings` loses the dev
  Application Info card.

**Backend identity:**

- Real `JwtBearer` validation against `https://login.microsoftonline.com/
  {TenantId}/v2.0` with audience = `api://{ClientId}`.
- New `Infrastructure/Auth/DatabaseRoleClaimsTransformation.cs`
  implementing `IClaimsTransformation`. Source of role claim is now the
  `Users` table (lookup by `oid`), with auto-creation on first login. The
  default role for new users is configurable
  (`Authorization:DefaultNewUserRole`).
- `CurrentUserService` claim fallbacks extended (`preferred_username`,
  `upn`, `email`, `unique_name`) so the email is reliably populated for
  first-time MSAL logins.

**Backend SharePoint integration:**

- New `Infrastructure/Services/AppGraphClient.cs` — wrapper around an
  app-only `GraphServiceClient` built from `Azure.Identity.
  ClientSecretCredential`. Coexists with the OBO client.
- `Azure.Identity` 1.13.1 added as a NuGet dependency.

**Backend SharePoint sync subsystem (entirely new):**

- `Domain/Entities/SharePointSyncState.cs` — persisted state per (SiteId,
  DriveId).
- `Persistence/Configurations/SharePointSyncStateConfiguration.cs` — EF
  mapping with a unique index on (SiteId, DriveId).
- `Application/Common/Interfaces/ISyncProcessor.cs` — contract.
- `Application/Features/Documents/Commands/RemoveDocumentCommand.cs` —
  cascades document deletion through to FAISS via the AI service.
- `Infrastructure/Services/SharePointSyncOptions.cs` — strongly-typed
  options for the new `SharePointSync` config section.
- `Infrastructure/Services/SharePointSyncProcessor.cs` — implements
  `ISyncProcessor`, calls Graph delta API, classifies items
  (Added/Modified/Deleted/Ignored), dispatches MediatR commands.
- `Infrastructure/Services/DeltaSyncService.cs` — `BackgroundService`
  with a `PeriodicTimer` polling at `PollingIntervalMinutes`.
- `Infrastructure/Services/SubscriptionRenewalService.cs` —
  `BackgroundService` creating and renewing Microsoft Graph webhook
  subscriptions on a 24 h timer.
- `Api/Controllers/WebhookController.cs` — anonymous endpoint accepting
  `POST /api/webhooks/sharepoint`. Handles the Graph validation handshake
  (echo `validationToken` as `text/plain` within 10 s) and verifies
  `clientState` via constant-time compare before dispatching.

**Persistence:**

- `Infrastructure/Migrations/` directory created — first real EF Core
  migrations replacing the previous `EnsureCreated()` bootstrap.

**AI service (minor):**

- `DELETE /api/documents/{id}` and `IngestDocumentAsync` extension on the
  backend client — completes the symmetry needed for sync (delete-
  then-reingest on Modified events, hard delete on Deleted events).

### Phase 4 — French RAG retrieval improvements + eval harness (6db6517, 2026-05-02)

Targeted at a class of failure observed during early French SOP
testing: the lexical half of the hybrid retriever was effectively
broken on French text. The fix is two surgical changes plus an eval
harness so future tuning can be measured rather than guessed.

**AI service — multilingual BM25 tokenizer:**

- `_tokenize` in `app/rag/bm25_store.py` was previously
  `text.lower().split()`. For French this meant `procédure`,
  `Procédure`, `procédures`, `procédure,` were four different tokens —
  catastrophic for recall and visible as bad fusion ranking downstream.
- Rewrite: NFC casefold → per-token script detection → French Snowball
  stemming via `PyStemmer` for Latin tokens; tashkeel stripping via
  `PyArabic` for Arabic tokens (never accent-fold Arabic — destroys
  hamza). French stoplist with negations preserved (`non`, `pas`,
  `aucun`).
- Index pickle now carries `BM25_INDEX_VERSION`; load discards
  mismatched-version pickles so on-disk indexes auto-rebuild on next
  ingest. Avoids the silent "old tokenization, new query" bug class.

**AI service — hierarchy-aware chunker (`RegulatoryChunker`):**

- New class in `app/services/chunking.py` alongside the original
  `TextChunker` (which remains the fallback for unstructured text).
- Detects document hierarchy via regex: `Chapitre`, `Article N`,
  numbered sections (`4`, `4.2`, `4.2.1`), and ALL-CAPS headings.
- Replaces the naive `[.!?]\s+` sentence splitter with `pysbd`
  configured for French — handles `Cf. Art.`, `n° 12`, decimals (`3.5`),
  and other French abbreviation patterns that previously broke
  mid-sentence.
- Each chunk gets a section breadcrumb prepended at index time:
  `SOP-001 › Chapitre 1 › Article 4 › 4.2.1 …`. Indexed by both FAISS
  (embedded) and BM25, so section-keyword matches surface naturally.
  Raw `Content` stored in SQL stays clean — the breadcrumb lives only
  in the index pickles, no schema change to the .NET-shared
  `TextSegments` table.
- Falls back gracefully to a single-section chunk for documents with
  no detected headings.

**AI service — eval harness (off until used):**

- New package `app/evals/`: strict JSONL goldset loader (intent /
  language enums, dedup IDs, line-pinpoint error messages),
  `ranx`-backed retrieval metrics (recall@k, MRR@10, nDCG@10), thin
  in-house LLM-as-judge for faithfulness and answer-relevance (skipped
  `ragas` — its langchain pinning conflicts with the project's
  `langchain-core==0.3.0`).
- Interactive CLI `python -m app.evals.bootstrap` — hits
  `/api/search?include_answer=false`, prints the top-k chunks with
  their `vector_store_id`, lets the user mark which are gold, appends
  one validated `GoldEntry` to `goldset.jsonl` atomically.

**AI service — operational tooling:**

- `scripts/reset_indexes.py` — wipe FAISS + BM25 from disk (dry-run by
  default).
- `scripts/ingest_local_files.py` — batch-ingest a folder of files
  bypassing the .NET DevController. Inserts the `Document` row
  directly via SQLAlchemy (committed in its own session because SQL
  Server's READ COMMITTED isolation hides uncommitted writes from
  the AI service's separate connection), POSTs to
  `/api/documents/ingest`, opens a *cleanup session* on AI failure to
  delete the orphan row.
- `scripts/run_eval.py` — load FAISS+BM25 from disk, walk goldset,
  print metrics. No HTTP server needed.

**Backend (minor):**

- `SearchResult.vector_store_id` is now populated (was always `""`).
  Required by the goldset bootstrap CLI to capture which chunks the
  user labels as gold.

**What was deliberately *not* done:** cross-encoder reranker, MMR /
dedup / token-budgeted context assembly, query planner with HyDE,
intent-conditioned prompts, faithfulness-based abstention. All
designed and considered (full plan archived) but premature without
a real goldset to verify against. Built once, deleted before
committing — the planning artifact remains.

---

## 2. Technology stack — additions and version movements

### Backend (.NET)

| Tech | Status at b26dea7 | Status today | Notes |
|---|---|---|---|
| .NET runtime | 8 (LTS) | 8 (LTS) | unchanged |
| ASP.NET Core MVC | ✅ minimal template | ✅ full controllers + middleware | added phase 2 |
| MediatR | ❌ | ✅ | added phase 1 |
| FluentValidation | ❌ | ✅ | added phase 1 |
| AutoMapper | ❌ | ✅ | added phase 1 |
| EF Core (`Microsoft.EntityFrameworkCore.SqlServer`) | ❌ | ✅ + migrations | added phase 2; migrations added phase 3 |
| Serilog (`Serilog.AspNetCore`, file sink) | ❌ | ✅ | added phase 2 |
| `Microsoft.Identity.Web` + `Microsoft.Identity.Web.MicrosoftGraph` | ❌ | ✅ | added phase 2 (config), wired phase 3 |
| `Microsoft.Graph` SDK | ❌ | ✅ (OBO) + ✅ (App-only via `Azure.Identity`) | OBO phase 2; app-only phase 3 |
| `Azure.Identity` (`ClientSecretCredential`) | ❌ | ✅ 1.13.1 | added phase 3 |
| Swashbuckle / Swagger | ✅ template default | ✅ | unchanged |

### AI service (Python)

| Tech | Status at b26dea7 | Status today | Notes |
|---|---|---|---|
| FastAPI / Uvicorn | ✅ | ✅ | unchanged |
| LangGraph | ✅ | ✅ | unchanged (graph extended in phase 2) |
| LangChain | ✅ | ✅ | unchanged |
| sentence-transformers (embedding model) | `all-MiniLM-L6-v2` (English) | `paraphrase-multilingual-MiniLM-L12-v2` (50 languages) | switched via env to support French docs; same 384-dim, no FAISS migration |
| FAISS (`faiss-cpu`) | ✅ | ✅ | unchanged |
| `rank_bm25` | ✅ | ✅ | tokenizer fully rewritten phase 4 (multilingual-aware) |
| `PyStemmer` | ❌ | ✅ 2.2.0.3 | added phase 4 (French Snowball stemming for BM25) |
| `PyArabic` | ❌ | ✅ 0.6.15 | added phase 4 (Arabic tashkeel stripping for BM25) |
| `pysbd` | ❌ | ✅ 0.3.4 | added phase 4 (French sentence segmentation in `RegulatoryChunker`) |
| `ranx` | ❌ | ✅ 0.3.20 (dev) | added phase 4 (eval harness retrieval metrics) |
| pypdf, python-docx, openpyxl, python-pptx | ✅ | ✅ | unchanged |
| SQLAlchemy + `aioodbc` | ✅ | ✅ | FreeTDS truncation fixed phase 2 |
| LLM providers | Azure OpenAI, Groq | Azure OpenAI, Groq, **Ollama** | Ollama added phase 1 |
| structlog | ✅ | ✅ | unchanged |
| pytest | ✅ | ✅ | unchanged |

### Frontend (React)

| Tech | Status at b26dea7 | Status today | Notes |
|---|---|---|---|
| React + TypeScript + Vite | ✅ | ✅ | unchanged |
| TailwindCSS | ✅ | ✅ | unchanged |
| React Router | ✅ | ✅ | unchanged |
| Recharts | ✅ | ✅ | unchanged |
| `@azure/msal-browser` + `@azure/msal-react` | ❌ | ✅ | added phase 3 |
| `lucide-react` icons | ✅ | ✅ | unchanged |

### Infrastructure / Docker

| Tech | Status at b26dea7 | Status today | Notes |
|---|---|---|---|
| `mcr.microsoft.com/mssql/server:2022-latest` | ✅ | ✅ | `platform: linux/amd64` for Apple Silicon |
| Docker Compose service graph | 4 services | 4 services | unchanged |
| Cloud IaC | `infrastructure/` empty | `infrastructure/` empty | not started |
| CI/CD | none | none | not started |

---

## 3. Architectural deltas vs `docs/architecture.md`

`docs/architecture.md` was written before phase 0 and froze a target
design. Four significant deltas have emerged.

### 3.1 Identity model: OBO-only → dual identity

`architecture.md` §5 describes a single auth path:

> User → Frontend → ASP.NET Core API → Microsoft Graph API → SharePoint

This is the **delegated/OBO** flow and remains in place for user-driven
operations (search, manual ingest). Phase 3 added a **second** path:

> Microsoft Graph (timer / webhook) → ASP.NET Core API
> → ASP.NET Core API (App-only Graph client) → SharePoint

Required because the background sync services have no user context to
exchange; OBO is impossible there. The two clients live side-by-side in DI
(`AppGraphClient` distinguishes the app-only one). The app-only client
uses `Sites.ReadWrite.All` *Application* permission; the delegated one
keeps `Files.Read.All`.

### 3.2 Document acquisition: pull-only → pull + push (sync subsystem)

`architecture.md` §7 describes a pull-only Hybrid RAG pipeline that starts
with "1. Document retrieval from SharePoint". The platform now also runs
a continuous sync loop:

```
SharePoint --(webhook)--> WebhookController --┐
                                              ├-> SharePointSyncProcessor
PeriodicTimer --> DeltaSyncService -----------┘     |
                                                    └-> MediatR (Ingest/Remove)
SubscriptionRenewalService keeps the webhook alive (≤30-day TTL).
```

This means:

- Documents are indexed *before* a user asks for them, eliminating the
  cold-start latency of the original on-demand flow.
- Deletions in SharePoint are reflected in FAISS + SQL Server within
  ~20 minutes (polling) or near-real-time (webhook).
- The platform tolerates webhook unavailability — `DeltaSyncService` is
  always-on as a safety net.

Webhook security relies on a `clientState` HMAC-checked at constant time
on each notification.

### 3.3 Role resolution: Entra App Roles → Database (`IClaimsTransformation`)

`architecture.md` §11 lists "role-based access control" as a security
mechanism but doesn't pin the source of truth. The original report
implicitly assumed Entra App Roles (`appRoles` in the manifest, assigned
via *Enterprise Applications → Users and groups*). That path required
admin permissions on the Sothema tenant that the project couldn't obtain.

Phase 3 introduced `DatabaseRoleClaimsTransformation`:

1. If the JWT already carries `ClaimTypes.Role`, the transformation is a
   no-op (forward path for a future Entra-driven setup).
2. Otherwise, look up the user by `oid` in `Users`; if missing,
   auto-create with the configured default role
   (`Authorization:DefaultNewUserRole`).
3. Append the role as a `ClaimTypes.Role` claim to the principal.

The change is **reversible**: as soon as Entra App Roles are assigned,
step 1 short-circuits and the DB is no longer consulted for role
resolution. Existing `[Authorize(Policy="RequireAdmin")]` decorators are
unchanged.

### 3.4 Persistence bootstrap: `EnsureCreated()` → EF Core migrations

Phase 2 used `EnsureCreated()` for fast local iteration. Phase 3 replaces
it with proper migrations — required for staging/production schema
evolution and zero-downtime deploys.

### 3.5 Domain model: 9 entities → 10 entities

Added: `SharePointSyncState` (Id, SiteId, DriveId, DeltaToken, LastSyncAt,
SubscriptionId, SubscriptionExpiry). Singleton-per-(Site,Drive). Lives in
the Domain layer but is **infrastructure-flavoured** — it has no
relations to the business model and is consulted only by sync services.

### 3.6 Hybrid RAG: language-agnostic → French-aware

`architecture.md` §7 describes the hybrid pipeline at the level of
"vector search + keyword search" — language-blind. Phase 4 specialised
both halves for French regulatory text:

- **Lexical (BM25)** is now French- and Arabic-aware: NFC casefold,
  per-token script detection, French Snowball stemming, Arabic
  tashkeel stripping, French stoplist with negations preserved.
- **Chunking** is now structure-aware: detects `Chapitre`/`Article`/
  numbered/ALL-CAPS headings, uses `pysbd` for French sentence
  segmentation, prepends a section breadcrumb to each chunk so section
  context is searchable for free.

These changes do not alter the architectural diagram — both stages
already existed as named components — but they make the previously
generic "hybrid retriever" specific to the deployed corpus
(pharmaceutical SOPs in French and Arabic). Behaviour falls back to
the original generic path for unstructured / non-French text.

Eval infrastructure (`app/evals/`) is added alongside but stays dormant
until a goldset is curated. No runtime impact when unused.

---

## 4. Component diagram — what's actually deployed today

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (React + MSAL)                                         │
│    AuthContext (MsalProvider) → ID Token                         │
└─────────────────────────────┬────────────────────────────────────┘
                              │ HTTPS (Bearer JWT)
┌─────────────────────────────▼────────────────────────────────────┐
│  Backend (ASP.NET Core 8)                                        │
│    Middleware: CorrelationId, JwtBearer, GlobalExceptionHandler  │
│    DatabaseRoleClaimsTransformation (DB-backed roles)            │
│    Controllers: Documents, Compliance, Search, Audit, Users,     │
│                 Health, Dev, Webhook (anonymous)                 │
│    Application: MediatR + ValidationBehavior + AuditBehavior     │
│    Infrastructure                                                │
│      ├── Repositories (EF Core)                                  │
│      ├── AiServiceClient (typed HttpClient)                      │
│      ├── SharePointService    (Graph OBO/delegated)              │
│      ├── StubSharePointService (dev only)                        │
│      └── Background services (gated on SharePointSync.Enabled)   │
│            ├── DeltaSyncService                                  │
│            ├── SubscriptionRenewalService                        │
│            └── SharePointSyncProcessor                           │
│                  └── AppGraphClient (Graph app-only)             │
└──────┬──────────────────────────────────────┬───────────────────┘
       │                                      │
       │ REST + X-API-Key                     │ Graph SDK
       ▼                                      ▼
┌────────────────────┐               ┌──────────────────┐
│  AI Service        │               │  Microsoft Graph │
│  (FastAPI, Python) │               │  + SharePoint    │
│  ├ RAG hybride     │               │  + Entra ID      │
│  ├ LangGraph (×6)  │               └──────────────────┘
│  └ Multi LLM       │
└─────────┬──────────┘
          │
          ▼
   ┌────────────────────────────┐
   │  Data layer                 │
   │  ├ SQL Server 2022          │
   │  └ FAISS + BM25 (volume)   │
   └────────────────────────────┘
```

Compared to `architecture.md` §2's high-level box-and-arrow diagram, the
*new* boxes are: MSAL, DatabaseRoleClaimsTransformation, WebhookController,
AppGraphClient, and the entire Background services package. The *new*
arrow is the inbound Graph→Webhook callback.

---

## 5. Drivers — why each change happened

| Change | Trigger |
|---|---|
| MediatR + behaviors | Decouple controllers from handlers; centralise audit + validation |
| Ollama provider | Develop offline, no API key required |
| Multilingual embedding model | Sothema's pharmaceutical documents are largely in French; the default English-only `all-MiniLM-L6-v2` returned poor recall on French queries — switched to `paraphrase-multilingual-MiniLM-L12-v2` |
| Stub SharePoint service | Run pipeline tests without an Entra tenant |
| Serilog + correlation ID | Cross-service tracing once both API and AI service log |
| MSAL frontend | Original architecture assumed Entra-issued JWT — needed a real client |
| DB-backed roles | Sothema tenant admins did not grant Entra App Role assignment |
| App-only Graph client | Background services have no user context — OBO impossible |
| SharePoint sync subsystem | Original on-demand flow had cold-start latency; users want documents searchable as soon as they are uploaded |
| EF Core migrations | Schema evolution beyond first deploy; can't ship `EnsureCreated()` |
| Sign-out UI | Required by users once MSAL was real (mock mode never logged out) |
| French BM25 tokenizer | `text.lower().split()` made `procédure`/`procédures`/`Procédure`/`procédure,` four different tokens — broke recall on French queries |
| Hierarchy-aware chunker | Naive `[.!?]\s+` regex split mid-sentence on `Cf. Art.`, `n° 12`, decimals; SOPs have explicit structure that should be exploited |
| Eval harness | Without measurement, every retrieval tuning change is faith-based |

---

## 6. Open items (not yet addressed)

These are explicitly out-of-scope for this changelog but worth flagging
so the gap to `docs/project-status.md` Priorities 1–4 is visible:

- **CI/CD** — no GitHub Actions yet.
- **Cloud IaC** — `infrastructure/` still empty.
- **Backend test suite** — empty `Sothema.Compliance.Tests` project.
- **Application Insights / OpenTelemetry** — Serilog is local only.
- **CORS lockdown** on the AI service (still `*`).
- **Removal of `DevController`** in production builds.
- **`langgraph 0.2.0` ↔ `langchain-openai 0.2.0` pin conflict** — blocks
  `pip install -r requirements.txt --strict` and `app.main` imports in
  `tests/test_api.py` (11 errors). Pre-existing; unrelated to phase 4
  changes.
- **RAG goldset** — eval harness is in place but the goldset is empty;
  retrieval tuning beyond the BM25 + chunker improvements should wait
  until ≥30 real labeled queries exist.

---

## 7. References

- `docs/architecture.md` — original target architecture (frozen pre-phase 0).
- `docs/project-status.md` — fine-grained per-area progress (auto-updated).
- `docs/sharepoint-sync-implementation-plan.md` — sync subsystem design rationale.
- `docs/credentials-setup-guide.md` — Entra ID + tunnel setup.
- `docs/report/main.tex` — formal report (chapter 3 design + chapter 4 realisation).
- `docs/report/changes-since-report.md` — UML-diagram-level changelog.
