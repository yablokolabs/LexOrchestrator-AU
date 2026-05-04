# LexOrchestrator-AU

Production-style FastAPI backend for jurisdiction-aware legal AI orchestration targeting Australian law firms. It combines multi-provider LLM routing, pgvector-backed RAG, citation traceability, feedback capture, graceful degradation, rate limiting, and basic Prometheus metrics.

> The bundled legal documents are synthetic mocks for development only. Replace them with licensed/authoritative sources before any client beta.

## What is implemented

- **FastAPI app** with `POST /query`, `POST /feedback`, `GET /health`, and `GET /metrics`.
- **LLM orchestration** with rules-based routing, OpenAI + Anthropic + Llama adapters, fallback chain, timeout, retry/backoff, circuit breakers, response normalization, and extractive fallback.
- **Jurisdiction-aware RAG** for AU legal material with document ingestion, section-aware chunking, batch embeddings, pgvector vector search, PostgreSQL full-text keyword search, metadata filters (`jurisdiction`, `court`, `case_type`, `doc_type`), and a simple reranker.
- **Source attribution** with `doc_id`, `chunk_id`, section, snippet, rank trace, and confidence scoring.
- **Feedback flywheel** storing query runs and feedback for future evaluation/fine-tuning datasets.
- **Stability features**: structured responses even on partial failure, request trace IDs, rate limiting, metrics, API drift-safe adapters.
- **Dockerized stack**: app + PostgreSQL/pgvector + Redis.

## Project layout

```text
src/lexorchestrator_au/
  adapters/        # OpenAI, Anthropic, Llama provider adapters
  api/             # FastAPI schemas/routes/query service
  attribution/     # citation and confidence scoring
  core/            # config, cache, metrics, middleware, rate limiting
  db/              # SQLAlchemy models/session/schema init
  feedback/        # query/feedback persistence
  orchestration/   # router, prompts, retry/fallback/circuit breaker
  rag/             # chunking, embeddings, repository, retrieval, ingestion
scripts/           # sample ingestion command
data/mock_legal_docs/
```

## Quick start with Docker

```bash
cd /home/azureuser/yablokolabs/LexOrchestrator-AU
cp .env.example .env
# Optional: set OPENAI_API_KEY and/or ANTHROPIC_API_KEY. Without keys, Llama extractive fallback runs.
docker compose up --build -d postgres redis app

docker compose --profile tools run --rm ingest
curl http://localhost:8000/health
```

Run a query:

```bash
curl -s http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{
    "query": "What factors determine whether a dismissal is harsh, unjust or unreasonable?",
    "jurisdiction": "AU",
    "court": "Fair Work Commission",
    "case_type": "employment",
    "max_citations": 4
  }' | jq
```

Record feedback:

```bash
curl -s http://localhost:8000/feedback \
  -H 'Content-Type: application/json' \
  -d '{
    "trace_id": "<trace_id from /query>",
    "rating": "correct",
    "comment": "Useful and cited correctly."
  }' | jq
```

Export corrected feedback examples for future evaluation/fine-tuning:

```bash
python scripts/export_feedback.py exports/feedback_dataset.jsonl
```

## Local development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp .env.example .env
uvicorn lexorchestrator_au.main:app --reload
```

If PostgreSQL is unavailable the app still starts and returns degraded structured responses; `/health` reports database degradation. For real retrieval, run PostgreSQL with pgvector and ingest documents.

## Configuration

Key environment variables:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://lex:lex@postgres:5432/lexorchestrator` |
| `REDIS_URL` | Optional Redis cache/rate-limit backend; in-memory fallback is used if unavailable |
| `OPENAI_API_KEY` | Enables OpenAI chat + optional embeddings |
| `ANTHROPIC_API_KEY` | Enables Anthropic Messages adapter |
| `LLAMA_API_URL` | Optional OpenAI-compatible local Llama/vLLM/Ollama endpoint |
| `EMBEDDING_PROVIDER` | `hash` for local deterministic dev embeddings or `openai` |
| `RATE_LIMIT_PER_MINUTE` | Per-process request limit |
| `LEX_API_KEYS` | Comma-separated API keys protecting `/query`, `/feedback`, and `/metrics`; leave unset only for local dev |
| `TRUST_PROXY_HEADERS` | Trust `x-forwarded-for` only when behind a configured trusted proxy |
| `CORS_ORIGINS` | Restrict firm portal origins; wildcard is dev-only |

## Data model

- `legal_documents`: authoritative document metadata and jurisdiction/court/case filters.
- `legal_chunks`: section-aware text chunks with pgvector embeddings and full-text search index.
- `query_runs`: query, normalized response, model, confidence, latency, and optional feedback fields.
- `feedback_events`: immutable feedback event log.

## Production beta notes

Before using with real firms:

1. Replace mock data with licensed Australian legal corpora and maintain source/version metadata.
2. Move schema changes to Alembic migrations; `auto_create_schema` is beta convenience.
3. Use provider-specific model allowlists and client-level data retention controls.
4. Set `LEX_API_KEYS`, restrict CORS, and put the service behind TLS, WAF, and tenant isolation.
5. Add evaluation sets for hallucination, citation accuracy, and jurisdiction leakage.
6. Tune pgvector indexes (`lists`, `probes`) for 100k+ documents and expected traffic.
7. Export `query_runs` + `feedback_events` into review queues before fine-tuning.

## API response contract

`POST /query` always returns structured data:

```json
{
  "trace_id": "uuid",
  "answer": "grounded answer",
  "citations": [
    {
      "citation_id": "C1",
      "doc_id": "uuid",
      "chunk_id": "uuid",
      "title": "...",
      "section": "Section 387",
      "snippet": "...",
      "trace": {"rank": 1, "vector_score": 0.81, "keyword_score": 0.14}
    }
  ],
  "confidence_score": 0.82,
  "model_used": "gpt-4o-mini",
  "provider": "openai",
  "degraded": false,
  "latency_ms": 842.4,
  "metadata": {"retrieved_chunks": 12}
}
```
