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
- **Backend API**: http://localhost:5000
- **AI Service**: http://localhost:8000
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

## License

This project is proprietary to Sothema.
