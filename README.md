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
