# LexOrchestrator-AU

Production-grade FastAPI backend for jurisdiction-aware legal AI orchestration targeting Australian law firms. Combines multi-provider LLM routing, pgvector-backed RAG, citation traceability, feedback capture, graceful degradation, rate limiting, and Prometheus metrics.

> **Note:** The bundled legal documents are synthetic mocks for development only. Replace them with licensed/authoritative sources before any client deployment.

## Architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        FastAPI Application                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐ │
│  │   Auth   │  │  Rate Limit  │  │  Trace ID  │  │   CORS   │ │
│  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘ │
│       └───────────────┼────────────────┼───────────────┘       │
│                       ▼                ▼                        │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    /v1/query endpoint                     │   │
│  │  QueryService → RetrievalService → LLMOrchestrator       │   │
│  │       ↓               ↓                  ↓               │   │
│  │  Attribution    pgvector + FTS     Adapters (fallback)    │   │
│  │  + Confidence   hybrid search      OpenAI → Anthropic    │   │
│  │                                    → Llama → extractive   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                       ▼                                         │
│  ┌──────────────────────────────────┐                          │
│  │   PostgreSQL/pgvector  │  Redis  │                          │
│  └──────────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- **Multi-provider LLM routing** with rules-based classification, fallback chains, circuit breakers, retry/backoff, and extractive degradation
- **Hybrid RAG pipeline** — pgvector cosine similarity + PostgreSQL full-text search with configurable fusion weights
- **Citation traceability** — every claim links back to `doc_id`, `chunk_id`, section, snippet, and retrieval scores
- **Feedback flywheel** — stores query runs and user feedback for evaluation and fine-tuning datasets
- **Production hardening** — structured JSON logging, Prometheus metrics, API key auth (timing-safe), rate limiting with LRU eviction, request trace IDs
- **Graceful degradation** — always returns structured responses, even when all LLM providers fail
- **API versioning** — `/v1/` prefix with backward-compatible legacy routes
- **Dockerized stack** — app + PostgreSQL/pgvector + Redis with resource limits and network isolation

## Project Layout

```text
src/lexorchestrator_au/
  adapters/        # OpenAI, Anthropic, Llama provider adapters
  api/             # FastAPI schemas, routes, query service
  attribution/     # Citation building and confidence scoring
  core/            # Config, cache, metrics, middleware, auth, rate limiting
  db/              # SQLAlchemy models, session management, schema init
  feedback/        # Query/feedback persistence and export
  orchestration/   # Router, prompts, retry/fallback, circuit breaker
  rag/             # Chunking, embeddings, repository, retrieval, reranking
scripts/           # CLI tools for ingestion and export
data/mock_legal_docs/  # Synthetic test data
tests/             # Unit and integration tests
```

## Quick Start

### Docker (recommended)

```bash
git clone <repo-url> && cd LexOrchestrator-AU
cp .env.example .env

# Set a database password (required)
sed -i 's/POSTGRES_PASSWORD=changeme/POSTGRES_PASSWORD=mysecretpassword/' .env

# Optional: add LLM provider keys for AI-powered responses
# Without keys, the system uses extractive fallback (no LLM calls)
# echo "OPENAI_API_KEY=sk-..." >> .env
# echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env

# Start the stack
docker compose up --build -d

# Ingest sample legal documents
docker compose --profile tools run --rm ingest

# Verify
curl http://localhost:8000/health | jq
```

### Local Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env

# Start PostgreSQL with pgvector (required for full functionality)
# Without it, the app starts in degraded mode

uvicorn lexorchestrator_au.main:app --reload
```

## Usage Examples

### Legal Research Query

```bash
curl -s http://localhost:8000/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What factors determine whether a dismissal is harsh, unjust or unreasonable under the Fair Work Act?",
    "jurisdiction": "AU",
    "court": "Fair Work Commission",
    "case_type": "employment",
    "max_citations": 4
  }' | jq
```

**Response:**
```json
{
  "trace_id": "a1b2c3d4-...",
  "answer": "Under section 387 of the Fair Work Act 2009 (Cth), the Commission must consider...",
  "citations": [
    {
      "citation_id": "C1",
      "doc_id": "uuid",
      "chunk_id": "uuid",
      "title": "Fair Work Act 2009 (Cth) — Unfair Dismissal Extract",
      "section": "Section 387",
      "snippet": "the Commission must take into account whether there was a valid reason...",
      "score": 0.82,
      "trace": { "rank": 1, "vector_score": 0.81, "keyword_score": 0.14 }
    }
  ],
  "confidence_score": 0.82,
  "model_used": "gpt-4o-mini",
  "provider": "openai",
  "degraded": false,
  "latency_ms": 842.4,
  "metadata": { "retrieved_chunks": 12 }
}
```

### Statutory Interpretation

```bash
curl -s http://localhost:8000/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What constitutes genuine redundancy under section 389?",
    "jurisdiction": "AU",
    "query_type": "statutory_interpretation"
  }' | jq
```

### Case Law Research

```bash
curl -s http://localhost:8000/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What precedent exists for procedural fairness requirements in administrative decisions?",
    "jurisdiction": "AU",
    "court": "High Court of Australia",
    "case_type": "administrative"
  }' | jq
```

### Drafting Assistance

```bash
curl -s http://localhost:8000/v1/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "Draft a clause addressing unfair dismissal protections for a new employment contract",
    "jurisdiction": "AU",
    "case_type": "employment"
  }' | jq
```

### Record Feedback

```bash
curl -s http://localhost:8000/v1/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "trace_id": "<trace_id from /v1/query response>",
    "rating": "correct",
    "comment": "Accurate citation of s387 factors. Well-structured."
  }' | jq
```

### Correct a Response (for fine-tuning)

```bash
curl -s http://localhost:8000/v1/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "trace_id": "<trace_id>",
    "rating": "partially_correct",
    "comment": "Missed the Small Business Fair Dismissal Code exception.",
    "corrected_answer": "Under section 385, a person has been unfairly dismissed if..."
  }' | jq
```

### Health Check

```bash
curl -s http://localhost:8000/v1/health | jq
```
```json
{
  "status": "ok",
  "app": "LexOrchestrator-AU",
  "database": "ok",
  "redis": "ok",
  "models": {
    "anthropic": "available",
    "openai": "available",
    "llama": "available"
  }
}
```

### Prometheus Metrics

```bash
curl -s http://localhost:8000/v1/metrics
```

### Export Feedback Dataset

```bash
# Via console script
lex-export-feedback exports/feedback_dataset.jsonl

# Or directly
python scripts/export_feedback.py exports/feedback_dataset.jsonl
```

### Using with API Keys (Production)

```bash
# Set API keys in .env
# LEX_API_KEYS=my-secret-key-1234567890abcdef,another-key-abcdef123456

curl -s http://localhost:8000/v1/query \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: my-secret-key-1234567890abcdef' \
  -d '{"query": "What is procedural fairness?", "jurisdiction": "AU"}' | jq
```

## Configuration

### Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `APP_ENV` | Environment mode (`development`, `test`, `staging`, `production`) | `development` |
| `DATABASE_URL` | Async SQLAlchemy connection string | Required in prod |
| `REDIS_URL` | Redis cache/rate-limit backend; in-memory fallback if unset | `None` |
| `OPENAI_API_KEY` | Enables OpenAI chat + embeddings | `None` |
| `ANTHROPIC_API_KEY` | Enables Anthropic Messages adapter | `None` |
| `LLAMA_API_URL` | OpenAI-compatible local Llama/vLLM/Ollama endpoint | `None` |
| `EMBEDDING_PROVIDER` | `hash` (local dev) or `openai` | `hash` |
| `RATE_LIMIT_PER_MINUTE` | Per-process request limit | `60` |
| `LEX_API_KEYS` | Comma-separated API keys (required in staging/production) | `""` |
| `CORS_ORIGINS` | Allowed CORS origins (wildcard blocked in production) | `["*"]` |
| `VECTOR_WEIGHT` | Hybrid search vector score weight | `0.70` |
| `KEYWORD_WEIGHT` | Hybrid search keyword score weight | `0.30` |
| `ANTHROPIC_MAX_TOKENS` | Max tokens for Anthropic responses | `4096` |

### Production Safety

When `APP_ENV` is `staging` or `production`, the app enforces:
- **No wildcard CORS** — `CORS_ORIGINS` must list explicit origins
- **API keys required** — `LEX_API_KEYS` must be set
- **Database URL required** — `DATABASE_URL` must be explicitly configured

## Data Model

| Table | Purpose |
|-------|---------|
| `legal_documents` | Document metadata, jurisdiction/court/case filters |
| `legal_chunks` | Section-aware text chunks with pgvector embeddings and FTS index |
| `query_runs` | Query, response, model, confidence, latency, and feedback fields |
| `feedback_events` | Immutable feedback event log for evaluation pipelines |

## Development

### Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=lexorchestrator_au --cov-report=term-missing
```

### Linting & Type Checking

```bash
ruff check src/ tests/
ruff format src/ tests/
mypy src/lexorchestrator_au/ --ignore-missing-imports
bandit -r src/lexorchestrator_au/ -c pyproject.toml
```

### CI/CD

The project includes a GitHub Actions workflow (`.github/workflows/ci.yml`) that runs on every push and PR:
- **Lint** — `ruff check` + `ruff format --check`
- **Type check** — `mypy`
- **Security** — `bandit`
- **Test** — `pytest` with coverage

## Production Deployment Notes

Before deploying with real law firms:

1. Replace mock data with licensed Australian legal corpora and maintain source/version metadata
2. Move schema changes to Alembic migrations; `auto_create_schema` is a beta convenience
3. Use provider-specific model allowlists and client-level data retention controls
4. Put the service behind TLS, WAF, and tenant isolation
5. Add evaluation sets for hallucination, citation accuracy, and jurisdiction leakage
6. Tune HNSW index parameters (`m`, `ef_construction`, `ef_search`) for your corpus size
7. Export `query_runs` + `feedback_events` into review queues before fine-tuning
8. Set `APP_ENV=production` to enforce security guardrails

## License

Proprietary — Yabloko Labs
