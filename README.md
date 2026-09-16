# AI Backend

A production-grade AI backend built incrementally with Python, FastAPI, and Groq.

## Quick Start

```bash
# Install dependencies
uv sync

# Set up environment
cp .env.example .env
# Edit .env with your Groq API key

# Run the server
uv run fastapi dev

# Run tests
uv run ruff check app/
```

## Docker Deployment

The full stack (app + Qdrant + observability) runs via Docker Compose.

```bash
# Start (first time or after code changes)
docker compose up -d --build

# Start (subsequent times)
docker compose up -d

# Follow app logs (JSON to stdout, also rotated in logs/app.log)
docker compose logs -f app

# Stop everything (keeps data and images)
docker compose down

# Stop and remove containers, images, and volumes
docker compose down -v --rmi all --remove-orphans
```

### Build cache & clean rebuilds

Dependencies are installed with uv using BuildKit cache mounts: uv's download/build caches
live on the host, so rebuilds reuse deps (npm-ci style) instead of re-downloading all ~474
transitive packages (the PyTorch / sentence-transformers stack).

```bash
# Normal rebuild — fast, deps served from the host-side uv cache
docker compose up -d --build

# Inspect what's taking disk space
docker system df

# Selective cache cleanup (safe: keeps containers, images, volumes, and data/)
docker builder prune -af          # clears build cache incl. the uv cache mounts
docker image prune -af            # clears unused/old images

# Full clean rebuild — nothing stale picked up, data still kept
docker compose down               # stop (keeps data/ + qdrant_storage/)
docker builder prune -af
docker image prune -af
docker compose build --no-cache --pull   # fresh layers + latest base images
docker compose up -d
```

- After `docker builder prune`, the next build does the full one-time dependency download
  (~5–10 min). uv's cache is content-addressed, so reuse is always safe; only Docker layers
  and images can go stale — cleared by `--no-cache --pull`.
- The uv caches are host-side mount caches, never baked into image layers, so images stay
  small and cache growth stays bounded.
- `data/`, `qdrant_storage/`, and `logs/` are host bind mounts — they survive every command
  above. Only `docker compose down -v` removes them (see warning below).

### Docker Desktop

Containers auto-restart when Docker Desktop launches. To manage they stack manually:
open **Docker Desktop → Containers**, select the `ai-backend` group, and use **Start**/**Stop**/**Restart**.

### Services

| Service   | URL                                   | Notes                              |
| --------- | ------------------------------------- | ---------------------------------- |
| API       | <http://localhost:8000>               | `/health` for status               |
| Grafana   | <http://localhost:3000>               | Anonymous auth, admin/admin        |
| Prometheus| <http://localhost:9090>               | Metrics                            |
| Qdrant    | <http://localhost:6333>               | Vector DB                          |
| Tempo     | <http://localhost:3200>               | Traces                             |
| Loki      | <http://localhost:3100>               | Logs                               |

> **Note:** `docker compose down -v` deletes Qdrant vectors, SQLite databases, logs, and API keys.

## API Endpoints

### Health
- `GET /health` — Server status

### Chat
- `POST /chat` — Basic LLM chat
- `POST /chat/tools` — Chat with tool calling
- `POST /agent` — Direct tool-calling agent
- `POST /agent/mcp` — MCP-based agent

### Embeddings
- `POST /embeddings` — Generate embeddings for text
- `POST /similarity` — Compare semantic similarity

### Documents
- `POST /documents` — Ingest a document
- `POST /search` — Search documents by similarity
- `DELETE /documents/{id}` — Delete a document

### RAG
- `POST /rag` — Answer questions using retrieved context

### Models
- `GET /models` — List available models
- `GET /models/{id}` — Get model details
- `POST /models` — Register a model

## Architecture

```
app/
├── main.py              # Composition root
├── routers/             # API endpoints
├── services/            # Business logic
servers/
├── documents.py         # MCP server
tools/
├── mcp_client.py        # MCP test client
```

## Development

```bash
# Lint
uv run ruff check app/
uv run ruff format app/

# Type check
uv run pyright

# Run MCP server standalone
PYTHONPATH=. uv run python servers/documents.py

# Test MCP server
PYTHONPATH=. uv run python tools/mcp_client.py documents
```

## Tech Stack

- **Python 3.14** with strict type checking
- **FastAPI** for HTTP API
- **Groq** via OpenAI SDK for LLM inference
- **sentence-transformers** for embeddings
- **MCP** for tool server protocol
- **Pydantic** for request validation
- **Ruff** for linting and formatting
- **uv** for dependency management

## Learning Progress

See [PROGRESS.md](PROGRESS.md) for the full teaching methodology and progress tracker.
