# Sothema AI Compliance Service — Architecture Documentation

## Table of Contents

- [1. High-Level Overview](#1-high-level-overview)
- [2. System Architecture](#2-system-architecture)
- [3. Multi-Agent Compliance Pipeline](#3-multi-agent-compliance-pipeline)
  - [3.1 Agent Overview](#31-agent-overview)
  - [3.2 LangGraph State Machine](#32-langgraph-state-machine)
  - [3.3 Shared State](#33-shared-state)
  - [3.4 Supervisor (Router)](#34-supervisor-router)
  - [3.5 Agent Details](#35-agent-details)
- [4. RAG Pipeline (Hybrid Retrieval)](#4-rag-pipeline-hybrid-retrieval)
  - [4.1 Vector Store (FAISS)](#41-vector-store-faiss)
  - [4.2 BM25 Keyword Store](#42-bm25-keyword-store)
  - [4.3 Reciprocal Rank Fusion (RRF)](#43-reciprocal-rank-fusion-rrf)
- [5. Document Processing Pipeline](#5-document-processing-pipeline)
  - [5.1 Text Extraction](#51-text-extraction)
  - [5.2 Chunking Strategy](#52-chunking-strategy)
  - [5.3 Embedding](#53-embedding)
- [6. LLM Service](#6-llm-service)
- [7. API Endpoints](#7-api-endpoints)
- [8. Database Schema](#8-database-schema)
- [9. End-to-End Workflow](#9-end-to-end-workflow)
- [10. Configuration Reference](#10-configuration-reference)

---

## 1. High-Level Overview

The Sothema AI Compliance Service is a Python FastAPI microservice that provides automated pharmaceutical regulatory compliance analysis. It ingests documents (PDF, DOCX, XLSX, PPTX, TXT), indexes them using a hybrid search engine, and runs a multi-agent LLM pipeline to evaluate compliance against GMP, ICH, FDA, WHO, and ISO standards.

**Key capabilities:**

- **Document Ingestion** — Extract text, chunk into token-aware segments, embed with sentence-transformers, and index into FAISS (vector) + BM25 (keyword) stores.
- **Hybrid Search** — Combine semantic vector search and BM25 keyword search using Reciprocal Rank Fusion (RRF).
- **Compliance Analysis** — A 6-agent LangGraph pipeline that retrieves context, analyzes content, evaluates regulatory alignment, scores compliance (0-100 across 4 categories), generates a stakeholder summary, and logs an audit trail.
- **Async Processing** — Analysis runs in the background; clients poll for results.

**Technology stack:**

| Component | Technology |
|-----------|------------|
| Framework | FastAPI + Uvicorn |
| Multi-Agent Orchestration | LangGraph (StateGraph) |
| LLM Providers | Groq (Llama 3.3 70B) or Azure OpenAI (GPT-4o) |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 (local, 384-dim) |
| Vector Search | FAISS IndexFlatIP (cosine similarity) |
| Keyword Search | BM25Okapi (rank-bm25) |
| Database | SQL Server (shared with .NET backend) |
| Async DB Driver | aioodbc (ODBC) |

---

## 2. System Architecture

```
                                  Sothema AI Compliance Platform
  ┌─────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                 │
  │  ┌──────────────┐     ┌────────────────────┐     ┌──────────────────────────┐  │
  │  │   Frontend    │────>│  .NET Backend API   │────>│  Python AI Service       │  │
  │  │   (React)     │     │  (ASP.NET Core)     │     │  (FastAPI)               │  │
  │  │   Port 3000   │     │  Port 5000          │     │  Port 8000               │  │
  │  └──────────────┘     └────────────────────┘     └──────────┬───────────────┘  │
  │                                │                             │                  │
  │                                │         ┌──────────────────┼──────────┐       │
  │                                │         │                  │          │       │
  │                                v         v                  v          v       │
  │                         ┌────────────┐ ┌──────┐    ┌─────────┐ ┌──────────┐   │
  │                         │ SQL Server │ │ FAISS│    │  BM25   │ │ Groq /   │   │
  │                         │ (shared)   │ │Index │    │  Index  │ │ Azure    │   │
  │                         │ Port 1433  │ │(disk)│    │ (disk)  │ │ OpenAI   │   │
  │                         └────────────┘ └──────┘    └─────────┘ └──────────┘   │
  └─────────────────────────────────────────────────────────────────────────────────┘
```

The AI Service operates as an independent microservice. The .NET backend creates `Document` records in SQL Server and calls the AI Service to ingest content and trigger compliance analysis. Both services share the same SQL Server database.

---

## 3. Multi-Agent Compliance Pipeline

### 3.1 Agent Overview

The compliance analysis pipeline consists of **6 specialized agents** orchestrated by a deterministic supervisor using LangGraph's `StateGraph`.

```
  ┌───────────────────────────────────────────────────────────────────┐
  │                    LangGraph StateGraph                          │
  │                                                                   │
  │  START                                                            │
  │    │                                                              │
  │    v                                                              │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Document Retrieval │  Hybrid RAG search   │
  │  │  (Router)     │    │ Agent              │  (FAISS + BM25)      │
  │  └──────┬───────┘    └────────┬──────────┘                       │
  │         │                     │                                   │
  │         v                     v                                   │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Content Analysis   │  LLM: Extract doc    │
  │  │  (Router)     │    │ Agent              │  structure & topics   │
  │  └──────┬───────┘    └────────┬──────────┘                       │
  │         │                     │                                   │
  │         v                     v                                   │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Regulatory         │  LLM: Evaluate vs    │
  │  │  (Router)     │    │ Compliance Agent   │  GMP/ICH/FDA/WHO     │
  │  └──────┬───────┘    └────────┬──────────┘                       │
  │         │                     │                                   │
  │         v                     v                                   │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Compliance Scoring │  LLM: 4x25 scoring   │
  │  │  (Router)     │    │ Agent              │  (JSON structured)    │
  │  └──────┬───────┘    └────────┬──────────┘                       │
  │         │                     │                                   │
  │         v                     v                                   │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Explanation Agent  │  LLM: Stakeholder     │
  │  │  (Router)     │    │                    │  summary (300-500w)   │
  │  └──────┬───────┘    └────────┬──────────┘                       │
  │         │                     │                                   │
  │         v                     v                                   │
  │  ┌──────────────┐    ┌───────────────────┐                       │
  │  │  Supervisor   │───>│ Audit Agent        │  DB: Log execution    │
  │  │  (Router)     │    │ (Terminal)         │  trace to AuditLogs   │
  │  └──────────────┘    └────────┬──────────┘                       │
  │                               │                                   │
  │                               v                                   │
  │                             END                                   │
  └───────────────────────────────────────────────────────────────────┘
```

### 3.2 LangGraph State Machine

The pipeline is defined in `app/agents/graph.py` as a LangGraph `StateGraph`. Each agent is a node, and conditional edges route between them through the supervisor.

**Graph construction:**

```python
graph = StateGraph(ComplianceState)

# Add nodes
graph.add_node("document_retrieval", doc_retrieval_node)
graph.add_node("content_analysis", content_analysis_node)
graph.add_node("regulatory_compliance", regulatory_node)
graph.add_node("compliance_scoring", scoring_node)
graph.add_node("explanation", explanation_node)
graph.add_node("audit", audit_node)

# Entry point → supervisor
graph.set_conditional_entry_point(route_next_agent)

# Each node → supervisor → next node
for node in ["document_retrieval", "content_analysis", "regulatory_compliance",
             "compliance_scoring", "explanation"]:
    graph.add_conditional_edges(node, route_next_agent)

# Audit is terminal
graph.add_edge("audit", END)
```

**Key design decision:** The pipeline is **deterministic and sequential**, not LLM-routed. The supervisor inspects the state to determine the next step. This ensures predictable execution order and simplifies debugging.

### 3.3 Shared State

All agents read from and write to a shared `ComplianceState` (TypedDict):

```python
class ComplianceState(TypedDict, total=False):
    # ── Input (set at pipeline start) ──
    job_id: str                      # ComplianceAnalysis.Id
    document_id: str                 # Document.Id
    document_content: str            # Extracted plain text
    document_title: str              # Document title

    # ── Agent outputs (accumulated sequentially) ──
    retrieved_segments: list[dict]   # Document Retrieval → RAG results
    content_analysis: str            # Content Analysis → structured summary
    regulatory_findings: list[dict]  # Regulatory Compliance → gap analysis
    scores: dict                     # Compliance Scoring → 4×25 breakdown
    explanation: str                 # Explanation → stakeholder summary
    audit_entries: list[dict]        # Audit → execution log

    # ── Control flow ──
    current_agent: str               # Last executed agent
    status: str                      # "pending" | "processing" | "completed" | "failed"
    error: str                       # Error message (triggers skip to audit)
```

### 3.4 Supervisor (Router)

The supervisor in `app/agents/supervisor.py` implements a `route_next_agent()` function that inspects the state and returns the name of the next node:

```python
def route_next_agent(state: ComplianceState) -> str:
    if state.get("error"):                    return "audit"
    if not state.get("retrieved_segments"):   return "document_retrieval"
    if not state.get("content_analysis"):     return "content_analysis"
    if not state.get("regulatory_findings"):  return "regulatory_compliance"
    if not state.get("scores"):               return "compliance_scoring"
    if not state.get("explanation"):          return "explanation"
    if not state.get("audit_entries"):        return "audit"
    return END
```

**Error handling:** If any agent sets the `error` field, the supervisor skips all remaining agents and routes directly to the audit agent, which logs the failure.

### 3.5 Agent Details

#### Agent 1: Document Retrieval

| Property | Value |
|----------|-------|
| **File** | `app/agents/document_retrieval.py` |
| **Purpose** | Retrieve relevant document segments using hybrid RAG |
| **Uses LLM** | No |
| **Dependencies** | HybridRetriever, EmbeddingService |

**Logic:**
1. Build search query from `document_title + first 500 chars of content`
2. Embed query using sentence-transformers (384-dim)
3. Run hybrid retrieval (FAISS vector + BM25 keyword + RRF fusion)
4. Return top 10 segments with relevance scores

**Output → State:**
```python
retrieved_segments: [
    {"vector_store_id": "uuid", "rrf_score": 0.016, "vector_rank": 1, "bm25_rank": null},
    ...
]
```

---

#### Agent 2: Content Analysis

| Property | Value |
|----------|-------|
| **File** | `app/agents/content_analysis.py` |
| **Purpose** | Extract structured information about the document |
| **Uses LLM** | Yes — `temperature: 0.1`, `max_tokens: 4096` |
| **Input** | `document_content` (truncated to 30,000 chars), `document_title` |

**System prompt:**
```
You are a pharmaceutical document content analyst.
Analyze the following document and provide a structured summary covering:

1. Document Type: What kind of document is this? (SOP, policy, guideline, report, etc.)
2. Key Topics: Main subjects and sections covered
3. Regulatory References: Any standards mentioned (GMP, ICH, FDA, EMA, etc.)
4. Process Descriptions: Key processes or procedures described
5. Critical Requirements: Important requirements or specifications stated
6. Defined Responsibilities: Roles and responsibilities mentioned

Provide a clear, structured analysis that can be used for compliance assessment.
```

**Output → State:**
```python
content_analysis: "## Document Type\nGMP Compliance Guide...\n## Key Topics\n..."
```

---

#### Agent 3: Regulatory Compliance

| Property | Value |
|----------|-------|
| **File** | `app/agents/regulatory_compliance.py` |
| **Purpose** | Evaluate document against pharmaceutical regulatory standards |
| **Uses LLM** | Yes — `temperature: 0.1`, `max_tokens: 4096` |
| **Input** | `content_analysis` (from Agent 2) |

**Evaluates against these frameworks:**
- GMP — EU GMP Annex guidelines
- ICH Q7 — Active Pharmaceutical Ingredients
- ICH Q10 — Pharmaceutical Quality System
- FDA 21 CFR Part 211 — CGMP for Finished Pharmaceuticals
- FDA 21 CFR Part 11 — Electronic Records / Signatures
- ISO 9001 — Quality Management Systems
- WHO GMP Guidelines

**System prompt asks for:**
- Requirements met
- Compliance gaps
- Risk areas (high/medium/low)
- Specific regulatory clause references
- Recommendations for each finding

**Output → State:**
```python
regulatory_findings: [
    {"raw_analysis": "Full LLM analysis text...", "agent": "regulatory_compliance"}
]
```

---

#### Agent 4: Compliance Scoring

| Property | Value |
|----------|-------|
| **File** | `app/agents/compliance_scoring.py` |
| **Purpose** | Generate a structured 0-100 compliance score |
| **Uses LLM** | Yes — JSON mode, structured output via Pydantic |
| **Input** | `regulatory_findings`, `content_analysis` |

**Scoring schema (4 categories, each 0-25 points):**

| Category | Max Score | What It Measures |
|----------|-----------|------------------|
| **Documentation** | 25 | Completeness, procedures described, version control |
| **Regulatory** | 25 | Alignment with GMP/ICH/FDA standards |
| **Quality** | 25 | QMS framework, CAPA processes, validation |
| **Traceability** | 25 | Audit readiness, records, responsibilities, workflows |

**Structured output format (Pydantic model, enforced via JSON mode):**
```python
class ComplianceScoreOutput(BaseModel):
    categories: dict[str, CategoryScore]  # 4 categories
    total_score: int                      # 0-100 (sum of categories)
    max_score: int = 100

class CategoryScore(BaseModel):
    score: int      # 0-25
    max: int = 25
    findings: list[str]  # Evidence supporting the score
```

**Output → State:**
```python
scores: {
    "categories": {
        "documentation": {"score": 20, "max": 25, "findings": ["...", "..."]},
        "regulatory":    {"score": 22, "max": 25, "findings": ["...", "..."]},
        "quality":       {"score": 18, "max": 25, "findings": ["...", "..."]},
        "traceability":  {"score": 15, "max": 25, "findings": ["...", "..."]}
    },
    "total_score": 75,
    "max_score": 100
}
```

---

#### Agent 5: Explanation

| Property | Value |
|----------|-------|
| **File** | `app/agents/explanation.py` |
| **Purpose** | Generate a human-readable compliance summary for stakeholders |
| **Uses LLM** | Yes — `temperature: 0.1`, `max_tokens: 4096` |
| **Input** | `scores`, `regulatory_findings`, `content_analysis`, `document_title` |

**The summary includes:**
1. Overall assessment statement
2. Score breakdown in plain language
3. Key compliance strengths
4. Areas for improvement (prioritized by risk)
5. Relevant regulatory references

**Output length:** 300-500 words
**Maps to:** `ComplianceAnalysis.Summary` in the database

---

#### Agent 6: Audit (Terminal)

| Property | Value |
|----------|-------|
| **File** | `app/agents/audit.py` |
| **Purpose** | Record the pipeline execution to the audit log |
| **Uses LLM** | No |
| **Database** | Writes to `AuditLogs` table |

**Audit record details:**
```python
AuditLog(
    UserId="ai-service",
    Action="ComplianceAnalysis",
    EntityType="ComplianceAnalysis",
    EntityId=job_id,
    Details=json.dumps({
        "document_title": str,
        "segments_retrieved": int,
        "has_content_analysis": bool,
        "has_regulatory_findings": bool,
        "scores": dict,
        "status": str,
        "error": str  # if pipeline failed
    })
)
```

---

## 4. RAG Pipeline (Hybrid Retrieval)

The search system combines two retrieval strategies and fuses them using Reciprocal Rank Fusion (RRF).

```
                     User Query
                         │
               ┌─────────┴─────────┐
               │                    │
               v                    v
    ┌────────────────┐   ┌────────────────┐
    │  FAISS Vector  │   │   BM25 Keyword │
    │  Search        │   │   Search       │
    │  (Semantic)    │   │   (Lexical)    │
    └───────┬────────┘   └───────┬────────┘
            │                    │
            │  Ranked results    │  Ranked results
            └────────┬───────────┘
                     │
                     v
           ┌──────────────────┐
           │  Reciprocal Rank │
           │  Fusion (RRF)    │
           │  k = 60          │
           └────────┬─────────┘
                    │
                    v
              Top-K Results
         (sorted by fused score)
```

### 4.1 Vector Store (FAISS)

| Property | Value |
|----------|-------|
| **File** | `app/rag/vector_store.py` |
| **Index Type** | `IndexFlatIP` (Inner Product) |
| **Dimensions** | 384 (from all-MiniLM-L6-v2) |
| **Similarity** | Cosine (via L2-normalized vectors + inner product) |
| **Persistence** | `data/faiss_indexes/faiss.index` + `faiss_meta.pkl` |

Vectors are L2-normalized at embedding time, so inner product equals cosine similarity. The metadata pickle maps FAISS row positions to `VectorStoreId` strings (UUIDs stored in the `TextSegments.VectorStoreId` SQL column).

### 4.2 BM25 Keyword Store

| Property | Value |
|----------|-------|
| **File** | `app/rag/bm25_store.py` |
| **Algorithm** | BM25Okapi (from `rank-bm25` library) |
| **Tokenization** | Lowercase + whitespace split |
| **Persistence** | `data/faiss_indexes/bm25_index.pkl` |

BM25 provides lexical matching — it excels at finding exact keyword matches that semantic search might miss (e.g., specific regulation codes like "ICH Q7" or "21 CFR Part 211").

### 4.3 Reciprocal Rank Fusion (RRF)

RRF combines two ranked lists into a single list. For each document that appears in either list:

```
RRF_score(d) = Σ  1 / (k + rank_i(d))
```

Where:
- `k = 60` (constant, prevents high-ranked items from dominating)
- `rank_i(d)` = rank of document `d` in retriever `i` (starting at 1)
- If `d` doesn't appear in a retriever's list, that term is 0

**Example:**
A document ranked #1 in vector search and #3 in BM25:
```
RRF = 1/(60+1) + 1/(60+3) = 0.01639 + 0.01587 = 0.03226
```

A document ranked #1 in vector search only (not in BM25):
```
RRF = 1/(60+1) + 0 = 0.01639
```

**Parameters:**
- `fetch_k = top_k × 2` — retrieve 2x candidates from each engine before fusion
- `top_k = 10` — return top 10 fused results

---

## 5. Document Processing Pipeline

```
  Base64 Content ──> Text Extraction ──> Token-Aware Chunking ──> Embedding ──> Dual Indexing
       │                   │                     │                    │              │
       v                   v                     v                    v              v
   Decode bytes    PDF/DOCX/XLSX/      Split into 512-token    all-MiniLM-L6-v2   FAISS +
                   PPTX/TXT parser     chunks with 50-token    384-dim vectors    BM25
                                       overlap                 (L2-normalized)    indexes
```

### 5.1 Text Extraction

**File:** `app/services/document_processor.py`

| Format | Library | Method |
|--------|---------|--------|
| PDF | `pypdf` | Extract text from all pages |
| DOCX | `python-docx` | Extract from paragraphs |
| XLSX | `openpyxl` | Extract from all cells across sheets |
| PPTX | `python-pptx` | Extract from slide text frames |
| TXT/MD | Built-in | UTF-8 decode |

### 5.2 Chunking Strategy

**File:** `app/services/chunking.py`

The chunker uses **token-aware splitting** with the `tiktoken` tokenizer (GPT-4o encoding):

| Parameter | Default | Description |
|-----------|---------|-------------|
| `chunk_size` | 512 tokens | Maximum tokens per chunk |
| `chunk_overlap` | 50 tokens | Overlap between consecutive chunks |

**Algorithm:**
1. Split text on paragraph boundaries (`\n\n`) and sentence endings (`.!?`)
2. Accumulate sentences until reaching 512 tokens
3. Create chunk; rewind overlap (last ~50 tokens of sentences)
4. For sentences longer than 512 tokens, split directly on token boundaries

**Output per chunk:**
```python
TextChunk(content: str, chunk_index: int, token_count: int)
```

### 5.3 Embedding

**File:** `app/services/embedding.py`

| Property | Value |
|----------|-------|
| **Model** | `sentence-transformers/all-MiniLM-L6-v2` |
| **Dimensions** | 384 |
| **Runs locally** | Yes — no API calls, cost-free |
| **Normalization** | L2-normalized (for cosine similarity via inner product) |
| **Download** | ~80MB on first run, then cached |

---

## 6. LLM Service

**File:** `app/services/llm.py`

The service supports two LLM providers, selectable via the `AI_SERVICE_LLM_PROVIDER` environment variable:

| Provider | Model | Use Case |
|----------|-------|----------|
| **Groq** | `llama-3.3-70b-versatile` | Free tier for development/testing |
| **Azure OpenAI** | `gpt-4o` | Production deployment |

**Groq** uses the OpenAI-compatible API (`https://api.groq.com/openai/v1`), so both providers use the same OpenAI client interface.

**Two generation modes:**

1. **Unstructured** (`generate`) — Returns free-form text. Used by Content Analysis, Regulatory Compliance, and Explanation agents.
   - `temperature: 0.1` (near-deterministic)
   - `max_tokens: 4096`

2. **Structured** (`generate_structured`) — Returns validated JSON matching a Pydantic schema. Used by the Compliance Scoring agent.
   - Uses `response_format: {"type": "json_object"}`
   - Appends JSON schema to the system message
   - Response is parsed and validated by Pydantic

**Retry logic:** 3 attempts with exponential backoff (1s, 2s, 4s).

---

## 7. API Endpoints

All endpoints except `/api/health` require an `X-API-Key` header.

### POST /api/documents/ingest

Ingest a document: extract text, chunk, embed, and index.

```
Request:
{
    "document_id": "uuid",          // Must already exist in Documents table
    "content": "base64-string",     // Base64-encoded file content
    "file_type": "pdf",             // pdf | docx | xlsx | pptx | txt
    "title": "Document Title"
}

Response:
{
    "document_id": "uuid",
    "segments_created": 3,
    "vectors_indexed": 3,
    "status": "success"
}
```

### GET /api/documents/{document_id}/status

Check ingestion status for a document.

```
Response:
{
    "document_id": "uuid",
    "title": "Document Title",
    "segment_count": 3,
    "indexed": true
}
```

### POST /api/search

Hybrid document search (vector + BM25 + RRF fusion).

```
Request:
{
    "query": "GMP calibration requirements",
    "top_k": 5                      // 1-50, default 10
}

Response:
{
    "query": "GMP calibration requirements",
    "results": [
        {
            "document_id": "uuid",
            "document_title": "GMP Guide",
            "segment_content": "Article 4: All equipment must be...",
            "chunk_index": 1,
            "relevance_score": 0.032,
            "vector_store_id": "uuid"
        }
    ],
    "total_results": 1
}
```

### POST /api/analyze

Trigger compliance analysis. Returns immediately; runs in background.

```
Request:
{
    "document_id": "uuid",
    "document_content": "base64-string",
    "file_type": "txt",
    "title": "GMP Compliance Guide"
}

Response:
{
    "job_id": "uuid",
    "status": "pending",
    "message": "Compliance analysis started"
}
```

### GET /api/analyze/{job_id}/status

Poll analysis status.

```
Response (completed):
{
    "job_id": "uuid",
    "status": "completed",
    "score": 75.0,
    "summary": "**Compliance Assessment Summary**\n\nThe document achieves 75/100...",
    "details": {
        "categories": {
            "documentation":  {"score": 20, "max": 25, "findings": [...]},
            "regulatory":     {"score": 22, "max": 25, "findings": [...]},
            "quality":        {"score": 18, "max": 25, "findings": [...]},
            "traceability":   {"score": 15, "max": 25, "findings": [...]}
        },
        "total_score": 75,
        "max_score": 100
    },
    "analyzed_at": "2026-03-24T12:10:01"
}
```

**Status values:** `pending` → `processing` → `completed` | `failed`

---

## 8. Database Schema

The AI Service shares a SQL Server database with the .NET backend. Table and column names use PascalCase to match EF Core conventions.

```
┌──────────────────┐       ┌─────────────────────┐
│    Documents     │       │   TextSegments      │
├──────────────────┤       ├─────────────────────┤
│ Id (PK)          │◄──────│ DocumentId (FK)     │
│ SharePointItemId │       │ Id (PK)             │
│ Title            │       │ Content             │
│ SiteId           │       │ ChunkIndex          │
│ DriveId          │       │ VectorStoreId  ─────────► FAISS + BM25 Indexes
│ ContentType      │       │ CreatedAt           │
│ FileType         │       └──────────┬──────────┘
│ SharePointUrl    │                  │
│ UploadedAt       │       ┌──────────┴──────────┐
└────────┬─────────┘       │ AiRequestSegments   │
         │                 ├─────────────────────┤
         │                 │ AiRequestId (PK,FK) │
         │                 │ TextSegmentId(PK,FK)│
         │                 │ RelevanceScore      │
         │                 └──────────┬──────────┘
         │                            │
         │                 ┌──────────┴──────────┐
         │                 │    AiRequests        │
         │                 ├─────────────────────┤
         │                 │ Id (PK)             │
         │                 │ UserQueryId (FK)    │
         │                 │ Question            │
         │                 │ Response            │
         │                 │ CreatedAt           │
         │                 └─────────────────────┘
┌────────┴─────────┐
│ComplianceAnalyses│       ┌─────────────────────┐
├──────────────────┤       │    AuditLogs        │
│ Id (PK)          │       ├─────────────────────┤
│ DocumentId (FK)  │       │ Id (PK)             │
│ Score (0-100)    │       │ UserId              │
│ Summary (MAX)    │       │ Action              │
│ Details (JSON)   │       │ EntityType          │
│ Status (0-3)     │       │ EntityId            │
│ AnalyzedAt       │       │ Timestamp           │
└──────────────────┘       │ Details (JSON)      │
                           └─────────────────────┘
```

**Key relationships:**
- `Documents` → `TextSegments` (1:N) — A document has many text chunks
- `Documents` → `ComplianceAnalyses` (1:N) — A document can be analyzed multiple times
- `TextSegments.VectorStoreId` — Links a DB record to its position in FAISS/BM25 indexes
- `AiRequests` → `AiRequestSegments` → `TextSegments` — Audit trail for search queries

---

## 9. End-to-End Workflow

### Document Ingestion Flow

```
1.  .NET Backend creates Document record in SQL Server
2.  .NET Backend calls POST /api/documents/ingest with base64 content
3.  AI Service verifies document exists in DB
4.  DocumentProcessor extracts plain text (PDF/DOCX/XLSX/PPTX/TXT)
5.  TextChunker splits into 512-token chunks with 50-token overlap
6.  EmbeddingService generates 384-dim vectors (all-MiniLM-L6-v2)
7.  TextSegment records created in DB (with VectorStoreId UUIDs)
8.  Vectors added to FAISS IndexFlatIP
9.  Text chunks added to BM25 index
10. Both indexes saved to disk
11. Response: {segments_created: N, vectors_indexed: N, status: "success"}
```

### Compliance Analysis Flow

```
1.  Client calls POST /api/analyze
2.  ComplianceAnalysis record created (Status=PENDING)
3.  Background task launched → returns job_id immediately
4.  Background task sets Status=PROCESSING

5.  ─── LangGraph Pipeline Starts ───

6.  [Document Retrieval Agent]
    • Builds query from title + first 500 chars
    • Embeds query → 384-dim vector
    • FAISS search → top 20 by cosine similarity
    • BM25 search → top 20 by keyword match
    • RRF fusion (k=60) → top 10 merged results
    → State: retrieved_segments populated

7.  [Content Analysis Agent]
    • Sends document text (≤30K chars) to LLM
    • LLM extracts: document type, topics, regulatory refs,
      processes, requirements, responsibilities
    → State: content_analysis populated

8.  [Regulatory Compliance Agent]
    • Sends content_analysis to LLM
    • LLM evaluates against GMP, ICH Q7, ICH Q10,
      FDA 21 CFR 211, FDA 21 CFR 11, ISO 9001, WHO GMP
    • Identifies gaps, risks, and recommendations
    → State: regulatory_findings populated

9.  [Compliance Scoring Agent]
    • Sends regulatory_findings + content_analysis to LLM (JSON mode)
    • LLM scores 4 categories (0-25 each):
      Documentation | Regulatory | Quality | Traceability
    • Response validated by Pydantic schema
    → State: scores populated (e.g., total_score: 75)

10. [Explanation Agent]
    • Sends scores + findings + analysis to LLM
    • LLM generates 300-500 word stakeholder summary
    • Covers: overall assessment, score breakdown, strengths,
      improvements (by risk), regulatory references
    → State: explanation populated

11. [Audit Agent]
    • Writes AuditLog record to DB
    • Logs: document_title, segments_retrieved, scores, status
    → State: audit_entries populated → END

12. ─── LangGraph Pipeline Complete ───

13. Background task extracts final state:
    • score = scores["total_score"]
    • summary = explanation
    • details = json.dumps(scores)
14. Updates ComplianceAnalysis: Status=COMPLETED
15. Client polls GET /api/analyze/{job_id}/status → gets full results
```

---

## 10. Configuration Reference

All settings are loaded from environment variables with the `AI_SERVICE_` prefix.

| Variable | Default | Description |
|----------|---------|-------------|
| `AI_SERVICE_API_KEY` | *(required)* | Shared API key for authentication |
| `AI_SERVICE_DATABASE_CONNECTION_STRING` | *(required)* | SQL Server ODBC connection string |
| `AI_SERVICE_LLM_PROVIDER` | `azure` | `"azure"` or `"groq"` |
| `AI_SERVICE_AZURE_OPENAI_ENDPOINT` | `""` | Azure OpenAI endpoint URL |
| `AI_SERVICE_AZURE_OPENAI_API_KEY` | `""` | Azure OpenAI API key |
| `AI_SERVICE_AZURE_OPENAI_API_VERSION` | `2024-06-01` | Azure API version |
| `AI_SERVICE_AZURE_OPENAI_CHAT_DEPLOYMENT` | `gpt-4o` | Azure deployment name |
| `AI_SERVICE_GROQ_API_KEY` | `""` | Groq API key |
| `AI_SERVICE_GROQ_MODEL` | `llama-3.3-70b-versatile` | Groq model ID |
| `AI_SERVICE_EMBEDDING_MODEL_NAME` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `AI_SERVICE_EMBEDDING_DIMENSIONS` | `384` | Embedding vector dimensions |
| `AI_SERVICE_FAISS_INDEX_PATH` | `data/faiss_indexes` | Path for FAISS/BM25 persistence |
| `AI_SERVICE_CHUNK_SIZE` | `512` | Tokens per chunk |
| `AI_SERVICE_CHUNK_OVERLAP` | `50` | Overlap tokens between chunks |
| `AI_SERVICE_RRF_K` | `60` | RRF fusion constant |
| `AI_SERVICE_TOP_K_RESULTS` | `10` | Default search results count |
| `AI_SERVICE_HOST` | `0.0.0.0` | Server bind address |
| `AI_SERVICE_PORT` | `8000` | Server port |
| `AI_SERVICE_LOG_LEVEL` | `info` | Logging level |
