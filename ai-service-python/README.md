# Sothema AI Compliance Service

Python FastAPI microservice providing document ingestion, hybrid RAG retrieval, and multi-agent compliance analysis for the Sothema AI Compliance Platform.

## Quick Start

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy and configure environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI and database credentials

# Run the service
uvicorn app.main:app --reload --port 8000
```

## API Endpoints

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/health` | No | Service health check |
| POST | `/api/documents/ingest` | API Key | Ingest a document (extract, chunk, embed, index) |
| DELETE | `/api/documents/{id}` | API Key | Remove document from indexes |
| GET | `/api/documents/{id}/status` | API Key | Check ingestion status |
| POST | `/api/search` | API Key | Hybrid document search |
| POST | `/api/analyze` | API Key | Trigger compliance analysis |
| GET | `/api/analyze/{jobId}/status` | API Key | Poll analysis status |

## Authentication

All endpoints except `/api/health` require an `X-API-Key` header matching the configured `AI_SERVICE_API_KEY`.

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Docker

```bash
docker build -t sothema-ai-service .
docker run -p 8000:8000 --env-file .env sothema-ai-service
```
