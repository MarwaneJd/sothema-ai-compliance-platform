# FastAPI AI Service — Implementation Plan

## Hybrid RAG + Multi-Agent Compliance Analysis

> **TL;DR** — Build the Python FastAPI microservice as the core intelligence layer of the platform. It handles document ingestion (text extraction, chunking, embedding), hybrid RAG retrieval (FAISS + BM25 with Reciprocal Rank Fusion), and multi-agent compliance analysis orchestrated via LangGraph. The service communicates exclusively with the ASP.NET Core backend (never directly with the frontend or SharePoint) and is authenticated via a shared API key (`X-API-Key` header). Both services share a SQL Server database — Python ORM models use PascalCase columns to match EF Core conventions.

---

## Table of Contents

- [Architecture Alignment](#architecture-alignment)
- [Integration Constraints](#integration-constraints)
- [Phase 1 — Project Scaffolding](#phase-1--project-scaffolding)
- [Phase 2 — Core Infrastructure](#phase-2--core-infrastructure)
- [Phase 3 — Document Processing Pipeline](#phase-3--document-processing-pipeline)
- [Phase 4 — Hybrid RAG Retrieval](#phase-4--hybrid-rag-retrieval)
- [Phase 5 — Document Ingestion Endpoints](#phase-5--document-ingestion-endpoints)
- [Phase 6 — Multi-Agent System (LangGraph)](#phase-6--multi-agent-system-langgraph)
- [Phase 7 — Search & Analysis Endpoints](#phase-7--search--analysis-endpoints)
- [Phase 8 — Containerization](#phase-8--containerization)
- [Phase 9 — Testing](#phase-9--testing)
- [Key Decisions](#key-decisions)
- [Verification Plan](#verification-plan)

---

## Architecture Alignment

This plan implements the **AI Processing Layer** as described in [`architecture.md`](architecture.md). It is responsible for:

- Document ingestion (text extraction, chunking, embedding generation)
- Hybrid document retrieval (vector search + keyword search)
- Multi-agent compliance analysis orchestrated via LangGraph
- Compliance scoring (0–100 scale, 4 categories of 25 points each)
- Audit trail logging for all AI operations

```
ASP.NET Core API → Python AI Service (FastAPI)
                     │
                     ├── Document Ingestion Pipeline
                     │     └── Extract → Chunk → Embed → Index (FAISS + BM25)
                     │
                     ├── Hybrid RAG Retrieval
                     │     └── Vector Search + BM25 → Reciprocal Rank Fusion
                     │
                     └── Multi-Agent Compliance Analysis (LangGraph)
                           └── Supervisor → Retrieval → Content Analysis
                               → Regulatory Compliance → Scoring → Explanation → Audit
```

---

## Integration Constraints

### Endpoint Contract with .NET Backend

The ASP.NET Core `AiServiceClient` calls these exact endpoints:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/ingest` | Ingest a document (extract, chunk, embed, index) |
| `DELETE` | `/api/documents/{id}` | Remove document from indexes |
| `GET` | `/api/documents/{id}/status` | Check ingestion status |
| `POST` | `/api/search` | Hybrid document search |
| `POST` | `/api/analyze` | Trigger compliance analysis (async) |
| `GET` | `/api/analyze/{jobId}/status` | Poll analysis status |
| `GET` | `/api/health` | Health check (no auth) |

### Shared Database — PascalCase Columns

Both services read/write the same SQL Server database. SQLAlchemy models use PascalCase column names to match EF Core defaults:

| Table | Key Columns |
|-------|-------------|
| `Documents` | `Id`, `SharePointItemId`, `Title`, `SiteId`, `DriveId`, `ContentType`, `FileType`, `SharePointUrl`, `UploadedAt` |
| `TextSegments` | `Id`, `DocumentId`, `Content`, `ChunkIndex`, `VectorStoreId`, `CreatedAt` |
| `ComplianceAnalyses` | `Id`, `DocumentId`, `Score`, `Summary`, `Details` (JSON string), `Status` (int), `AnalyzedAt` |
| `AuditLogs` | `Id`, `UserId`, `Action`, `EntityType`, `EntityId`, `Timestamp`, `Details` |
| `Users` | `Id`, `EntraObjectId`, `DisplayName`, `Email`, `Role` (int) |
| `Agents` | `Id`, `Name`, `TaskType`, `IsActive` |
| `UserQueries` | `Id`, `UserId`, `Question`, `Response`, `AgentId`, `CreatedAt` |
| `AiRequests` | `Id`, `UserQueryId`, `Question`, `Response`, `CreatedAt` |
| `AiRequestSegments` | `AiRequestId`, `TextSegmentId`, `RelevanceScore` |

### Enum Storage as Integers

| Enum | Values |
|------|--------|
| `AnalysisStatus` | Pending=0, Processing=1, Completed=2, Failed=3 |
| `UserRole` | Admin=0, Analyst=1, Viewer=2 |

### Key Bridge Field

`TextSegment.VectorStoreId` connects FAISS index entries to SQL records. Generated as a UUID string by the AI service during ingestion, stored in both the FAISS metadata map and the SQL column.

---

## Phase 1 — Project Scaffolding

### Project Structure

```
ai-service-python/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app + lifespan (FAISS/BM25 load)
│   ├── config.py                  # pydantic-settings (env vars, AI_SERVICE_ prefix)
│   ├── dependencies.py            # FastAPI Depends (DB sessions, services, stores)
│   ├── api/
│   │   ├── routes/
│   │   │   ├── documents.py       # POST /api/documents/ingest, DELETE, GET status
│   │   │   ├── search.py          # POST /api/search
│   │   │   ├── analysis.py        # POST /api/analyze, GET /api/analyze/{jobId}/status
│   │   │   └── health.py          # GET /api/health (no auth)
│   │   └── schemas/
│   │       ├── documents.py       # Ingest request/response models
│   │       ├── search.py          # Search request/response models
│   │       └── analysis.py        # Analysis request/response + scoring models
│   ├── core/
│   │   ├── security.py            # X-API-Key header validation via secrets.compare_digest
│   │   └── exceptions.py          # Custom exceptions + FastAPI handlers
│   ├── services/
│   │   ├── document_processor.py  # Text extraction (PDF, DOCX, XLSX, PPTX, TXT)
│   │   ├── chunking.py            # Token-aware splitting via tiktoken
│   │   ├── embedding.py           # sentence-transformers all-MiniLM-L6-v2 (384 dims, local)
│   │   └── llm.py                 # Azure OpenAI chat wrapper (JSON mode support)
│   ├── rag/
│   │   ├── vector_store.py        # FAISS IndexFlatIP + id_map + disk persistence
│   │   ├── bm25_store.py          # BM25Okapi + serialization
│   │   ├── hybrid_retriever.py    # RRF fusion (k=60), merges vector + BM25
│   │   └── pipeline.py            # Query → embed → retrieve → fetch segments → LLM → answer
│   ├── agents/
│   │   ├── state.py               # ComplianceState TypedDict
│   │   ├── supervisor.py          # Deterministic router (no LLM needed)
│   │   ├── document_retrieval.py  # Hybrid retrieval → state.retrieved_segments
│   │   ├── content_analysis.py    # LLM content extraction → state.content_analysis
│   │   ├── regulatory_compliance.py # GMP/ICH/FDA checks → state.regulatory_findings
│   │   ├── compliance_scoring.py  # 4×25 rubric scoring → state.scores
│   │   ├── explanation.py         # Human-readable summary → state.explanation
│   │   ├── audit.py               # Write AuditLog records → terminal node
│   │   └── graph.py               # StateGraph build + compile
│   └── db/
│       ├── session.py             # SQLAlchemy async engine (mssql+aioodbc)
│       ├── models.py              # All 9 ORM models (PascalCase columns)
│       └── repositories.py        # Async repos for all entities
├── data/
│   └── faiss_indexes/             # .gitignore'd — persisted FAISS + BM25 indexes
├── tests/
│   ├── conftest.py                # Fixtures: test client, mock DB, mock LLM
│   ├── test_document_processor.py
│   ├── test_chunking.py
│   ├── test_hybrid_retriever.py
│   ├── test_agents.py
│   └── test_api.py
├── requirements.txt
├── requirements-dev.txt
├── Dockerfile
├── .env.example
├── .gitignore
└── README.md
```

### Dependencies (`requirements.txt`)

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.9.0
pydantic-settings==2.5.0
python-multipart==0.0.9
sqlalchemy[asyncio]==2.0.35
aioodbc==0.5.0
pyodbc==5.1.0
langchain-openai==0.2.0
langchain-core==0.3.0
langgraph==0.2.0
faiss-cpu==1.8.0
rank-bm25==0.2.2
sentence-transformers==3.0.0
openai==1.45.0
tiktoken==0.7.0
numpy==1.26.4
pypdf==4.3.0
python-docx==1.1.0
openpyxl==3.1.5
python-pptx==1.0.0
structlog==24.4.0
httpx==0.27.0
```

### Environment Variables (`.env.example`)

All variables use the `AI_SERVICE_` prefix to avoid collisions with .NET backend env vars in docker-compose.

| Variable | Description | Default |
|----------|-------------|---------|
| `AI_SERVICE_API_KEY` | Shared secret for backend auth | (required) |
| `AI_SERVICE_DATABASE_CONNECTION_STRING` | SQL Server ODBC connection string | (required) |
| `AI_SERVICE_AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint URL | (required) |
| `AI_SERVICE_AZURE_OPENAI_API_KEY` | Azure OpenAI API key | (required) |
| `AI_SERVICE_AZURE_OPENAI_API_VERSION` | API version | `2024-06-01` |
| `AI_SERVICE_AZURE_OPENAI_CHAT_DEPLOYMENT` | Chat model deployment name | `gpt-4o` |
| `AI_SERVICE_EMBEDDING_MODEL_NAME` | Local sentence-transformers model | `all-MiniLM-L6-v2` |
| `AI_SERVICE_EMBEDDING_DIMENSIONS` | Embedding vector dimensions | `384` |
| `AI_SERVICE_FAISS_INDEX_PATH` | Path to FAISS index directory | `data/faiss_indexes` |
| `AI_SERVICE_CHUNK_SIZE` | Chunk size in tokens | `512` |
| `AI_SERVICE_CHUNK_OVERLAP` | Chunk overlap in tokens | `50` |
| `AI_SERVICE_RRF_K` | RRF constant | `60` |
| `AI_SERVICE_TOP_K_RESULTS` | Default number of results | `10` |

---

## Phase 2 — Core Infrastructure

### Configuration (`app/config.py`)

Pydantic `BaseSettings` with `env_prefix="AI_SERVICE_"`. All settings are configurable via environment variables, enabling model swaps (e.g., GPT-4o → GPT-5.2) without code changes. Embeddings use a local sentence-transformers model (no Azure OpenAI costs).

### Security (`app/core/security.py`)

FastAPI dependency using `APIKeyHeader(name="X-API-Key")`. Validates against the configured secret using `secrets.compare_digest` for timing-safe comparison. Returns 401 on mismatch.

Applied as a router-level dependency on all `/api/*` routes except `/api/health`.

### Exception Handling (`app/core/exceptions.py`)

Custom exceptions with FastAPI exception handlers:

| Exception | HTTP Status | Use Case |
|-----------|-------------|----------|
| `DocumentNotFoundError` | 404 | Document not in database |
| `DocumentProcessingError` | 422 | Text extraction or chunking failure |
| `EmbeddingError` | 500 | Local embedding model failure |
| `LLMError` | 502 | Azure OpenAI chat API failure |
| `RetrievalError` | 500 | FAISS/BM25 search failure |
| `AnalysisError` | 500 | Agent pipeline failure |
| `VectorStoreError` | 500 | FAISS index operation failure |

### Database (`app/db/`)

- **`session.py`** — Async SQLAlchemy engine via `mssql+aioodbc` dialect with connection pooling
- **`models.py`** — All 9 ORM models with PascalCase columns, `UNIQUEIDENTIFIER` primary keys, integer enum storage
- **`repositories.py`** — Async data access: `DocumentRepository`, `TextSegmentRepository`, `ComplianceAnalysisRepository`, `AuditLogRepository`, `AiRequestRepository`, `AiRequestSegmentRepository`

### Application Entry Point (`app/main.py`)

FastAPI app with:
- **Lifespan handler**: loads FAISS + BM25 indexes on startup, saves on shutdown
- **CORS middleware**: allows .NET backend origin
- **Exception handlers**: registered from `core/exceptions.py`
- **Router registration**: health (no auth), documents/search/analysis (with API key dependency)

---

## Phase 3 — Document Processing Pipeline

### Text Extraction (`app/services/document_processor.py`)

Accepts file bytes + file type, routes to the appropriate extractor:

| File Type | Library | Approach |
|-----------|---------|----------|
| PDF | `pypdf` | Page-by-page text extraction |
| DOCX | `python-docx` | Paragraph text extraction |
| XLSX | `openpyxl` | Flatten cells to pipe-delimited rows per sheet |
| PPTX | `python-pptx` | Extract text from all shapes per slide |
| TXT/MD | Built-in | UTF-8 decode |

### Text Chunking (`app/services/chunking.py`)

Token-aware recursive text splitter:
- Uses `tiktoken` with the GPT-4o tokenizer for accurate token counting
- Splits on paragraph boundaries first, then sentence boundaries
- Configurable `chunk_size` (default 512 tokens) and `chunk_overlap` (default 50 tokens)
- Returns `TextChunk(content, chunk_index, token_count)` objects

### Embedding Service (`app/services/embedding.py`)

Local embedding generation using `sentence-transformers` with `all-MiniLM-L6-v2` (384 dimensions):
- Free, open-source, runs locally on CPU (~80MB model)
- No API calls needed — zero cost, no latency from external services
- Model loaded once at startup via `SentenceTransformer(model_name)`, stored in `app.state`
- L2-normalizes all vectors before returning (for cosine similarity via FAISS inner product)

### LLM Service (`app/services/llm.py`)

Azure OpenAI chat completion wrapper:
- `generate()` — Standard text generation with configurable temperature/max_tokens
- `generate_structured()` — JSON mode for agents needing parseable responses (e.g., scoring)
- Built-in retry logic and token usage tracking via `structlog`

---

## Phase 4 — Hybrid RAG Retrieval

### FAISS Vector Store (`app/rag/vector_store.py`)

- Index type: `faiss.IndexIDMap(faiss.IndexFlatIP(384))` — inner product on normalized vectors = cosine similarity
- Maintains bidirectional mapping: FAISS int ID ↔ `VectorStoreId` string
- Methods: `load()`, `save()`, `add_vectors()`, `search()`, `remove_vectors()`
- Persists to `data/faiss_indexes/` (index file + metadata pickle)

### BM25 Keyword Store (`app/rag/bm25_store.py`)

- Uses `rank_bm25.BM25Okapi` with whitespace + lowercase tokenization
- Parallel `corpus_ids` list mapping position → `VectorStoreId`
- Rebuilt on every add/remove (BM25Okapi doesn't support incremental updates)
- Serialized to disk alongside FAISS index

### Hybrid Retriever (`app/rag/hybrid_retriever.py`)

Reciprocal Rank Fusion combining both search methods:

```
1. Fetch 2×top_k from FAISS vector search
2. Fetch 2×top_k from BM25 keyword search
3. For each result: RRF_score = Σ 1/(k + rank)  with k=60
4. Sort by RRF score descending, return top_k
```

Returns `RetrievedSegment(vector_store_id, rrf_score, vector_rank, bm25_rank)`.

### RAG Pipeline (`app/rag/pipeline.py`)

End-to-end pipeline: embed query → hybrid retrieve → fetch segments from DB → build context prompt → call LLM → return answer with source references.

---

## Phase 5 — Document Ingestion Endpoints

### `POST /api/documents/ingest`

**Request**: `{ document_id, content (base64), file_type, title }`

**Flow**:
1. Verify `Document` record exists in SQL (created by .NET backend)
2. Decode base64 → extract text → chunk with tiktoken
3. Generate embeddings via local sentence-transformers model
4. Create `TextSegment` rows in SQL (with generated `VectorStoreId`)
5. Add vectors to FAISS index + texts to BM25 index
6. Save indexes to disk

**Response**: `{ document_id, segments_created, vectors_indexed, status }`

> **Important**: The .NET backend creates the `Document` record first, then calls this endpoint. The AI service only creates `TextSegment` records.

### `DELETE /api/documents/{document_id}`

Removes TextSegments from DB and vectors from FAISS/BM25 (for re-indexing when documents are updated).

### `GET /api/documents/{document_id}/status`

Returns segment count and whether all segments are indexed.

---

## Phase 6 — Multi-Agent System (LangGraph)

### Shared State (`app/agents/state.py`)

```python
class ComplianceState(TypedDict, total=False):
    job_id: str                           # ComplianceAnalysis.Id
    document_id: str
    document_content: str                 # Extracted plain text
    document_title: str
    retrieved_segments: list[dict]        # From document retrieval
    content_analysis: str                 # From content analysis
    regulatory_findings: list[dict]       # From regulatory compliance
    scores: dict                          # 4×25 category breakdown
    explanation: str                      # Human-readable summary
    audit_entries: list[dict]             # From audit agent
    current_agent: str
    status: str                           # "pending"|"processing"|"completed"|"failed"
    error: str
```

### Agent Pipeline

| Agent | LLM? | Input | Output |
|-------|------|-------|--------|
| **Supervisor** | No (deterministic) | Full state | Routes to next agent based on populated fields |
| **Document Retrieval** | No | Document content | `retrieved_segments` via hybrid retriever |
| **Content Analysis** | Yes | Document text | Structured content summary (document type, topics, regulatory references, processes) |
| **Regulatory Compliance** | Yes | Content analysis | Compliance findings against GMP, ICH Q7/Q10, FDA 21 CFR 211, WHO GMP |
| **Compliance Scoring** | Yes (JSON mode) | Regulatory findings | 4×25 category scores: documentation, regulatory, quality, traceability |
| **Explanation** | Yes | Scores + findings | Human-readable assessment summary (300–500 words) |
| **Audit** | No | Full state | Writes `AuditLog` records to SQL Server |

### LangGraph Flow (`app/agents/graph.py`)

```
Entry → Supervisor → Document Retrieval → Supervisor → Content Analysis
      → Supervisor → Regulatory Compliance → Supervisor → Compliance Scoring
      → Supervisor → Explanation → Supervisor → Audit → END
```

Each agent returns to the supervisor, which deterministically routes to the next agent. On error, the supervisor skips to the audit agent.

### Scoring → Database Mapping

| State Field | SQL Column |
|-------------|------------|
| `scores["total_score"]` | `ComplianceAnalysis.Score` (0–100) |
| `explanation` | `ComplianceAnalysis.Summary` |
| JSON of `scores` dict | `ComplianceAnalysis.Details` |
| Pipeline status | `ComplianceAnalysis.Status` (0–3) |

### Scoring Categories

| Category | Max | What It Measures |
|----------|-----|------------------|
| Documentation | 25 | Completeness, procedure clarity, version control |
| Regulatory | 25 | Alignment with GMP, ICH, FDA standards |
| Quality | 25 | Quality controls, CAPA processes, validation |
| Traceability | 25 | Audit readiness, responsibility assignment, review workflows |

---

## Phase 7 — Search & Analysis Endpoints

### `POST /api/search`

**Request**: `{ query, top_k }`

Direct hybrid retrieval (no agents):
1. Embed query → hybrid retrieve → fetch segments + parent documents from DB
2. Create `AiRequest` + `AiRequestSegment` records for audit trail
3. Return ranked results with relevance scores and document metadata

### `POST /api/analyze`

**Request**: `{ document_id, document_content (base64), file_type, title }`

Async analysis:
1. Create `ComplianceAnalysis` record with `Status=Pending(0)`
2. Launch background task via `asyncio.create_task`
3. Return `{ job_id, status: "pending" }` immediately

**Background task**:
1. Update status to `Processing(1)`
2. Extract text from document
3. Run the full LangGraph compliance pipeline
4. Update `ComplianceAnalysis` with Score, Summary, Details, `Status=Completed(2)`
5. On error: set `Status=Failed(3)`

### `GET /api/analyze/{jobId}/status`

Returns current status and results (if completed):
- `{ job_id, status, score, summary, details, analyzed_at }`

---

## Phase 8 — Containerization

### Dockerfile

```dockerfile
FROM python:3.12-slim
# Install ODBC Driver 18 for SQL Server
# pip install requirements
# Copy app code
# Expose 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Docker Compose (`docker/docker-compose.yml`)

```yaml
services:
  sqlserver:
    image: mcr.microsoft.com/mssql/server:2022-latest
    ports: ["1433:1433"]

  backend-api:
    build: ../backend-dotnet-api
    ports: ["5000:8080"]
    environment:
      - AiService__BaseUrl=http://ai-service:8000

  ai-service:
    build: ../ai-service-python
    ports: ["8000:8000"]
    environment:
      - AI_SERVICE_API_KEY=${AI_SERVICE_API_KEY}
      - AI_SERVICE_DATABASE_CONNECTION_STRING=...
      - AI_SERVICE_AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      - AI_SERVICE_AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
    volumes:
      - faiss-data:/app/data/faiss_indexes
    depends_on: [sqlserver]
```

---

## Phase 9 — Testing

### Test Structure

| Test File | Scope | Key Assertions |
|-----------|-------|----------------|
| `test_document_processor.py` | Unit | Each file type extracts expected text; unsupported types raise error |
| `test_chunking.py` | Unit | Chunk sizes respect limits; overlap works; edge cases (empty, tiny) |
| `test_hybrid_retriever.py` | Unit | RRF fusion ranks correctly; documents in both lists rank highest |
| `test_agents.py` | Unit | Supervisor routing: correct sequence through all agents; error handling |
| `test_api.py` | Integration | Auth (valid/invalid/missing key); endpoint validation; health check |

### Test Configuration

- `conftest.py` provides fixtures: test client, mock vector/BM25 stores, mock embedding/LLM services
- Environment variables set via `os.environ` defaults for test isolation
- Uses `TestClient` (sync) for API tests, `pytest-asyncio` for async unit tests

---

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **PascalCase SQLAlchemy columns** | Must match EF Core defaults since both services share the same SQL Server database |
| **Enum storage as integers** | Matches C# enum default behavior (Pending=0, Processing=1, etc.) |
| **Deterministic supervisor routing** | Sequential pipeline doesn't need LLM-based routing — saves tokens and latency |
| **Background task for analysis** | Analysis is long-running (multiple LLM calls); POST returns immediately with job_id for polling |
| **VectorStoreId as UUID string** | Generated by Python during ingestion, stored in both FAISS id_map and TextSegment.VectorStoreId |
| **AI_SERVICE_ env prefix** | Avoids collisions with .NET backend env vars in docker-compose |
| **`aioodbc` with pyodbc fallback** | `aioodbc` may have maturity issues; test first, fall back to sync pyodbc + `run_in_executor` if needed |
| **L2-normalized vectors + IndexFlatIP** | Inner product on normalized vectors = cosine similarity; simpler than IndexFlatL2 |
| **LLM model configurable via env var** | Start with GPT-4o, switch to GPT-5.2 by changing `AI_SERVICE_AZURE_OPENAI_CHAT_DEPLOYMENT` |
| **Embedding model: all-MiniLM-L6-v2** | 384 dimensions — free, local, no API costs. Good accuracy for regulatory text retrieval |
| **RRF with k=60** | Proven effective fusion method; no tunable weights needed |
| **Compliance scoring: 4×25 = 0–100** | Transparent, additive breakdown; each category independently assessable |
| **FAISS persistence on every ingestion** | Acceptable for single-instance deployment; revisit if scaling horizontally |
| **pip + requirements.txt** | Simple dependency management; sufficient for this project's needs |

---

## Verification Plan

### Build & Startup

```bash
pip install -r requirements.txt        # installs without errors
uvicorn app.main:app --reload           # starts on port 8000
```

### Endpoint Tests

| Test | Method | URL | Expected |
|------|--------|-----|----------|
| Health check | `GET` | `/api/health` | 200 with FAISS/BM25/DB status |
| Auth rejection | `POST` | `/api/search` (no key) | 401 |
| Auth acceptance | `POST` | `/api/search` (valid key) | passes auth |
| Ingest document | `POST` | `/api/documents/ingest` | `segments_created > 0` |
| Search | `POST` | `/api/search` | Ranked chunks with scores |
| Trigger analysis | `POST` | `/api/analyze` | `job_id` + `status: "pending"` |
| Poll analysis | `GET` | `/api/analyze/{jobId}/status` | Transitions: pending → processing → completed |

### Database Verification

- `ComplianceAnalysis` record has `Score`, `Summary`, `Details` populated after analysis completes
- `AuditLog` entries created for each analysis
- `TextSegment.VectorStoreId` populated for all ingested segments

### Docker

```bash
docker build -t sothema-ai-service ai-service-python/
docker run -p 8000:8000 --env-file .env sothema-ai-service
# Service responds on http://localhost:8000/api/health
```

### Unit Tests

```bash
cd ai-service-python
pytest tests/ -v
```

All tests should pass.

---

## Implementation Order

| Phase | Deliverable | Depends On |
|-------|-------------|------------|
| **1** | Project structure, requirements, .env, .gitignore | — |
| **2** | Config, security, exceptions, DB models, repositories, main.py | Phase 1 |
| **3** | Document processor, chunking, embedding, LLM services | Phase 1 |
| **4** | FAISS store, BM25 store, hybrid retriever, RAG pipeline | Phase 2, 3 |
| **5** | Document ingestion endpoints + schemas | Phase 2, 3, 4 |
| **6** | All 7 agents + LangGraph graph | Phase 4 |
| **7** | Search + analysis endpoints | Phase 4, 5, 6 |
| **8** | Dockerfile, docker-compose entry | Phase 7 |
| **9** | Tests (unit + integration) | All phases |

> Each phase produces a functional increment that can be tested independently.
