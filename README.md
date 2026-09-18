# AI Backend

A production-grade RAG + agent chatbot backend built incrementally with Python, FastAPI,
and Groq. It answers questions with retrieval-augmented generation, runs LLM agents with
tool calling (including an MCP tool server), background-ingests documents through a
durable job queue, and ships a full observability stack (Prometheus, Grafana, Loki,
Tempo, OpenTelemetry).

> 📖 **Why it exists, the ideology behind it, and every deliberate tradeoff are in
> [THE-STORY.md](THE-STORY.md).** Operational details live in `AGENTS.md`.

## Quick Start

```bash
# Install dependencies
uv sync

# Set up environment (needs a Groq API key and, for embeddings, an HF token)
cp .env.example .env
# Edit .env with your GROQ_API_KEY (HF_TOKEN too if you want embeddings/RAG)

# Run the server
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000

# Create an API key (every endpoint except /health, /metrics needs one)
PYTHONPATH=. uv run python tools/manage_keys.py create <name>
```

## Auth

All functional endpoints require a bearer API key (`Authorization: Bearer ak_live_...`),
stored only as a SHA-256 hash. Manage keys with:

```bash
PYTHONPATH=. uv run python tools/manage_keys.py list          # show keys + status
PYTHONPATH=. uv run python tools/manage_keys.py create demo   # create a key
PYTHONPATH=. uv run python tools/manage_keys.py revoke 1      # revoke by id
```

Rate limiting is per-key (60 req/min by default, configurable), in-process — valid for
the single uvicorn worker; see `RATE_LIMIT_STRATEGY=redis` for multi-worker deployments.

## Docker Deployment

The full stack (app + Qdrant + observability) runs via Docker Compose.

```bash
# Start (first time or after code changes)
docker compose up -d --build

# Start subsequent times (reuses the existing image — no rebuild)
docker compose up -d

# Follow app logs (JSON to stdout, also rotated in logs/app.log)
docker compose logs -f app

# Stop (keeps containers, images, and data)
docker compose down
```

> ⚠️ **`docker compose down -v` deletes Qdrant vectors, SQLite databases (API keys
> included), and logs.** Never run it casually.

### Build cache & pinned images

- Dependencies are installed with uv using BuildKit cache mounts: rebuilds reuse deps
  (npm-ci style) instead of re-downloading all ~474 transitive packages.
- Every image is pinned to a proven tag (qdrant, otel-collector-contrib, prometheus,
  tempo, loki, promtail, grafana; base `python:3.14.7-slim`), so stacks are reproducible.
- `data/`, `qdrant_storage/`, and `logs/` are host bind mounts — they survive every
  command above. Only `docker compose down -v` removes them.

```bash
# Inspect disk usage / prune safely (keeps data/)
docker system df
docker builder prune -af          # clears build cache incl. the uv cache mounts
docker image prune -af            # clears unused/old images
```

### Services

| Service    | URL                             | Notes                              |
| ---------- | ------------------------------- | ---------------------------------- |
| API        | <http://localhost:8000>         | `/health`, `/health/ready`         |
| Grafana    | <http://localhost:3000>         | Anonymous auth (dev default)       |
| Prometheus | <http://localhost:9090>         | Metrics                            |
| Qdrant     | <http://localhost:6333>         | Vector DB                          |
| Tempo      | <http://localhost:3200>         | Traces                             |
| Loki       | <http://localhost:3100>         | Logs                               |

## API Endpoints

| Method | Path                     | Description                                          |
| ------ | ------------------------ | ---------------------------------------------------- |
| GET    | `/health`                | Liveness probe                                       |
| GET    | `/health/ready`          | Readiness (Qdrant + SQLite)                          |
| POST   | `/chat`                  | Basic LLM chat (`stream=true` → SSE)                 |
| POST   | `/chat/tools`            | Chat with tool calling (`stream=true` → SSE)         |
| POST   | `/agent`                 | Direct tool-calling agent (`stream=true` → SSE)      |
| POST   | `/agent/mcp`             | Agent using the MCP tool server                      |
| POST   | `/agent/graph`           | LangGraph-based agent (no streaming)                 |
| POST   | `/embeddings`            | Embed a list of texts (HF Inference API)             |
| POST   | `/similarity`            | Cosine similarity between two texts                  |
| POST   | `/documents`             | Enqueue document ingestion (202 + poll `/jobs`)      |
| GET    | `/documents/metadata`    | List document metadata                               |
| DELETE | `/documents/{id}`        | Delete a document (vector + metadata)                |
| POST   | `/search`                | Semantic search over documents                       |
| POST   | `/rag`                   | Answer a question with retrieved context             |
| GET    | `/models` / `/models/{id}` / `POST /models` | Model registry (SQLite-persisted) |
| GET    | `/jobs` / `/jobs/{id}`   | Background job listing / polling                     |
| GET    | `/fetch`                 | SSRF-guarded HTTP proxy (authenticated)              |
| GET    | `/metrics`               | Prometheus metrics                                   |
| GET    | `/slow/*`                | Demo endpoints (only when `DEMO_ENDPOINTS=true`)     |

## Architecture

```
app/
├── main.py              # Composition root
├── routers/             # API endpoints
├── services/            # Business logic (LLM, RAG, worker, stores, ...)
servers/
├── documents.py         # MCP tool server (stdio)
tools/
├── manage_keys.py       # API key management
├── run_eval.py          # RAG quality gate (LLM-as-judge)
├── stream_test.py       # SSE contract test
├── mcp_client.py        # MCP test client
├── test_agent_graph.py  # Agent behavior test
```

## Development

```bash
# Lint / typecheck / test (must be clean before committing)
uv run ruff check app/ servers/ tools/ tests/
uv run pyright app/ servers/
uv run pytest                      # hermetic unit tests
AI_BACKEND_KEY=<key> uv run pytest -m integration   # live-stack tests (Docker up)

# Smoke checks
PYTHONPATH=. uv run python tools/stream_test.py      # needs API_KEY env
PYTHONPATH=. uv run python tools/run_eval.py         # RAG quality gate
PYTHONPATH=. uv run python tools/mcp_client.py documents
```

CI (`.github/workflows/lint.yml`) runs ruff + pyright strict + the hermetic unit suite +
a docker build on every push.

## Tech Stack

- **Python 3.14** with strict type checking (pyright), ruff linting, uv packaging
- **FastAPI** (async) — routers, Pydantic validation, SSE streaming
- **Groq** via the OpenAI SDK for LLM inference (model centralized in `app/config.py`)
- **Hugging Face Inference Providers** for embeddings (no local model downloads)
- **Qdrant** vector DB (COSINE, deterministic UUID5 point IDs)
- **SQLite** (WAL) for metadata, jobs, API keys, model registry
- **LangGraph** for the graph agent; **MCP** for the tool server
- **OpenTelemetry + Prometheus + Grafana + Loki + Tempo** observability stack

## Learning Progress

The full teaching methodology, phase-by-phase build history, best practices, and the
known tradeoffs (with rationale) are documented in [THE-STORY.md](THE-STORY.md).