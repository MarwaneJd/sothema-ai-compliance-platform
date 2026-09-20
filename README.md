# Sothema AI Compliance Platform

An AI-powered pharmaceutical compliance analysis platform that helps regulatory and quality teams search, analyze, and understand compliance documents using Hybrid RAG and multi-agent AI systems.

Built for **Sothema** — integrates with SharePoint document repositories and Microsoft enterprise services.

---

## Architecture

```
Frontend (React + TypeScript + TailwindCSS)
        │
        ▼
Backend API (ASP.NET Core)  ──►  Microsoft Graph API  ──►  SharePoint
        │
        ▼
AI Service (Python FastAPI + LangGraph)
        │
        ├── Hybrid RAG Pipeline (FAISS + BM25)
        └── Multi-Agent System
              ├── Document Retrieval Agent
              ├── Content Analysis Agent
              ├── Regulatory Compliance Agent
              ├── Compliance Scoring Agent
              ├── Explanation Agent
              └── Audit Agent
```

---

## Tech Stack

| Layer              | Technology                                      |
| ------------------ | ----------------------------------------------- |
| Frontend           | React 19, TypeScript, TailwindCSS 4, Vite       |
| Backend API        | ASP.NET Core (.NET 9)                            |
| AI Service         | Python, FastAPI, LangGraph, LangChain            |
| LLM                | Azure OpenAI (GPT-4o) / Groq (Llama 3.3)        |
| Embeddings         | Sentence-Transformers (paraphrase-multilingual-MiniLM-L12-v2) |
| Vector Database    | FAISS                                            |
| Relational Database| SQL Server 2022                                  |
| Authentication     | Microsoft Entra ID (OAuth2 / OIDC)               |
| Documents          | Microsoft SharePoint via Graph API               |
| Containerization   | Docker & Docker Compose                          |

---

## Project Structure

```
sothema-ai-compliance-platform/
├── frontend-web/            # React SPA
├── backend-dotnet-api/      # ASP.NET Core API (Clean Architecture)
│   └── src/
│       ├── Sothema.Compliance.Api/            # Web API layer
│       ├── Sothema.Compliance.Application/    # Application logic
│       ├── Sothema.Compliance.Domain/         # Domain entities
│       └── Sothema.Compliance.Infrastructure/ # Data access & external services
├── ai-service-python/       # Python AI microservice
│   └── app/
│       ├── agents/          # LangGraph multi-agent system
│       ├── rag/             # Hybrid RAG pipeline (FAISS + BM25)
│       ├── services/        # Document processing, embeddings, LLM
│       ├── db/              # Database models & repositories
│       └── core/            # Security & exception handling
├── docker/                  # Docker Compose & environment config
├── docs/                    # Architecture & implementation plans
└── infrastructure/          # Deployment configuration
```

---

## Getting Started

### Prerequisites

- **Node.js** >= 18
- **Python** >= 3.12
- **.NET SDK** >= 9.0
- **Docker & Docker Compose**
- **SQL Server** (or use the Docker Compose setup)

### Quick Start with Docker

```bash
# 1. Clone the repository
git clone https://github.com/MarwaneJd/sothema-ai-compliance-platform.git
cd sothema-ai-compliance-platform

# 2. Configure environment variables
cp docker/.env.example docker/.env
# Edit docker/.env with your actual credentials

# 3. Start all services
cd docker
docker compose up --build
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:5001 (Swagger at `/swagger`)
- **AI Service**: http://localhost:8000 (health at `/api/health`)
- **SQL Server**: localhost:1433

### Local Development

#### Frontend
```bash
cd frontend-web
npm install
npm run dev          # http://localhost:5173
```

#### Backend API
```bash
cd backend-dotnet-api
dotnet restore
dotnet run --project src/Sothema.Compliance.Api
```

#### AI Service
```bash
cd ai-service-python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Configure your API keys
uvicorn app.main:app --reload --port 8000
```

---

## Environment Configuration

Each service has its own environment configuration:

| File                              | Purpose                          |
| --------------------------------- | -------------------------------- |
| `docker/.env.example`             | Docker Compose environment vars  |
| `ai-service-python/.env.example`  | AI service configuration         |
| `frontend-web/.env.development`   | Frontend API endpoint config     |

Copy `.env.example` files to `.env` and fill in your credentials before running.

> **Important**: Never commit `.env` files containing real API keys or secrets.

---

## Key Features

- **Intelligent Document Search** — Semantic + keyword hybrid search over SharePoint documents
- **Automated Compliance Analysis** — AI-driven regulatory compliance evaluation
- **Compliance Scoring** — Quantified compliance scores with explanations
- **Explainable AI** — Transparent reasoning with source document references
- **Audit Trail** — Full traceability of all AI interactions and decisions
- **Multi-Agent System** — Specialized AI agents collaborating via LangGraph
- **Enterprise Integration** — SharePoint, Entra ID, Azure OpenAI

---

## Engineering Highlights

A few parts of the system that went beyond wiring an LLM to a vector store.

### Retrieval is hybrid, fused, and reranked

Dense vectors alone underperform on regulatory text, where exact identifiers
(`Article 4.2.1`, batch codes, product names) matter as much as meaning. The
pipeline runs FAISS and BM25 in parallel, fuses the two ranked lists with
Reciprocal Rank Fusion, then reorders the survivors with a
`bge-reranker-v2-m3` cross-encoder. The score surfaced to the API is the
cross-encoder relevance, not the raw RRF value — RRF scores are tiny and
non-comparable across queries, so they're useless to show a user.
See [`app/rag/`](ai-service-python/app/rag/).

### Chunking respects document structure

A naive splitter cuts regulatory documents mid-article and destroys the
context a retrieved passage needs to be interpretable. `RegulatoryChunker`
detects numbered sections, `Article N`, `Chapitre N` and all-caps headings,
refuses to split across article boundaries unless an article runs past 2×
the target size, and emits a section-path breadcrumb prepended to the text at
index time. See [`app/services/chunking.py`](ai-service-python/app/services/chunking.py).

### The corpus is French, so the models are multilingual

Embeddings use `paraphrase-multilingual-MiniLM-L12-v2` rather than a default
English-only model — an easy detail to get wrong that quietly halves retrieval
quality on a non-English corpus.

### The agent loop has a hard budget

Agentic retrieval can loop indefinitely or burn unbounded tokens. The budget is
wall-clock, iteration and LLM-call capped, enforced in state rather than exposed
as an LLM-controlled field, and on exhaustion the graph routes to generation with
whatever has been retrieved so far instead of failing.
See [`app/agents/agentic_rag/budget.py`](ai-service-python/app/agents/agentic_rag/budget.py).

### Retrieval quality is measured, not assumed

An eval harness scores `recall@k`, `MRR` and `nDCG` against a hand-labeled
59-query goldset, plus LLM-as-judge faithfulness and answer-relevance, so
changes to chunking, fusion or reranking can be A/B'd instead of eyeballed.
Metrics are computed in-house with no extra dependencies.
See [`app/evals/`](ai-service-python/app/evals/).

### SharePoint sync is incremental

Documents sync through Microsoft Graph delta queries with persisted sync state,
so re-syncs transfer only what changed rather than rebuilding the corpus.
See [`DeltaSyncService.cs`](backend-dotnet-api/src/Sothema.Compliance.Infrastructure/Services/DeltaSyncService.cs).

### The .NET API follows Clean Architecture

Four projects with dependencies pointing inward — `Domain` holds entities and
knows nothing of infrastructure, `Application` holds logic behind interfaces,
`Infrastructure` provides EF Core persistence and external services (SharePoint,
Graph), and `Api` is the thin web layer. External services sit behind interfaces
with stub implementations, so the stack runs end-to-end without live Microsoft
365 credentials.

---

## Testing

```bash
cd ai-service-python && pytest
```

The Python suite covers chunking, BM25, hybrid retrieval, the agent graph,
document processing, the eval harness and the API surface. The .NET test
project is currently scaffolding only — backend coverage is the main
outstanding gap.

---

## License

This project is proprietary to Sothema.
