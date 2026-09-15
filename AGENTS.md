# AGENTS.md — Operating Manual for AI Backend

This file is the source of truth for any agent working on this repo. Read it fully before
changing anything. It describes **what the app is**, **how to run/verify it**, and the
**execution roadmap** in priority order (each item is a separate commit).

---

## 1. What This App Is

A "production-grade" RAG (Retrieval-Augmented Generation) + agent chatbot backend.

- **Stack:** Python 3.14 (uv), FastAPI, Groq LLM (OpenAI SDK), Qdrant vector DB, SQLite,
  LangGraph, MCP, OpenTelemetry, Prometheus/Grafana/Loki/Tempo/Promtail.
- **Architecture:** `/usr/local/bin`-style separation — `app/` (FastAPI), `servers/` (MCP),
  `tools/` (CLI scripts), `config/` (Docker/observability configs), `data/` (SQLite + Qdrant).
- **Inference:** Groq, model `qwen/qwen3.8-27b` (see Phase 2 — must become configurable).
- **Chrome-color note:** Docker image currently ships ONLY `app/` (`.dockerignore` excludes
  `servers`, `tools`, `config`). This is a known gap (Phase 3, issue).

### Key entry points
- `app/main.py` — FastAPI app, router registration, lifespan (worker thread, dotenv load).
- `app/dependencies.py` — auth (`require_api_key`), `require_rate_limit`, `PROTECTED` guard.
- `app/services/llm.py` — Groq client + tool definitions + SSE streaming + usage logging.
- `app/services/vector_store.py` — Qdrant client singleton (`QDRANT_URL` env, default localhost:6333).
- `app/services/worker.py` — background job loop for async document ingestion.
- `app/routers/` — `health`, `models`, `demo`, `chat`, `embeddings`, `documents`, `rag`, `jobs`, `metrics`.
- `docker-compose.yml` — 8 services (app, qdrant, otel-collector, tempo, prometheus, loki, promtail, grafana).

---

## 2. How to Verify the App (run these, don't guess)

All of the following must pass before any "done" claim.

### Local dev (no Docker)
```bash
uv sync
cp .env.example .env   # must have valid GROQ_API_KEY
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Docker stack
```bash
docker compose up -d --build
curl -s http://localhost:8000/health          # → {"status":"ok"}
```

### Test API key (create one if needed)
```bash
PYTHONPATH=. uv run python tools/manage_keys.py create <name>
```

### Core smoke tests
```bash
# chat (non-stream)
curl -s -X POST http://localhost:8000/chat \
  -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
  -d '{"message":"Say hello in one short sentence."}'

# embeddings + similarity
curl -s -X POST http://localhost:8000/similarity \
  -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
  -d '{"text_a":"hello","text_b":"world"}'

# async document ingest → poll job
curl -s -X POST http://localhost:8000/documents \
  -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
  -d '{"text":"Qdrant is a vector database.","metadata":{"source":"smoke"}}'
curl -s http://localhost:8000/jobs/<job_id> -H "Authorization: Bearer <KEY>"

# RAG end-to-end
curl -s -X POST http://localhost:8000/rag \
  -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
  -d '{"question":"What is RAG?"}'
```

### Eval / tools
```bash
PYTHONPATH=. uv run python tools/run_eval.py          # RAG quality gate
PYTHONPATH=. uv run python tools/stream_test.py       # SSE contract
PYTHONPATH=. uv run python tools/test_agent_graph.py  # agent behavior
PYTHONPATH=. uv run python tools/mcp_client.py documents   # MCP server smoke
```

### Lint / typecheck
```bash
uv run ruff check app/                       # must be clean
uv run pyright app/services/job_store.py app/services/worker.py   # per-file only (whole repo is slow)
```

### Observability quick checks
```bash
curl -s http://localhost:9090/api/v1/query?query=ai_backend:error_ratio:5m   # → value, not empty
curl -s "http://localhost:3200/api/search?tags=service.name%3D%22ai-backend%22&limit=1"  # traces exist
curl -s "http://localhost:3100/loki/api/v1/labels"   # logs flowing
curl -s http://localhost:3000/api/search?type=dash-db   # "RAG Overview" provisioned
```

---

## 3. Repo Conventions (FOLLOW THESE)

- **Commits:** one logical change per commit. Conventional style from history:
  `[FEAT]: ...`, `[FIX]: ...`, `[DOCS]: ...`, `[CI]: ...`. Imperative mood, concise body.
- **No comments in code unless asked.** No new files unless required.
- **Python:** match existing style (type hints, TypedDicts, service modules over fat routers).
- **Secrets:** never commit `.env`, keys, or the literal `ak_live_*`/`sk-*` values. `.env` is safe.
- **Do NOT run `docker compose down -v` casually** — it wipes `data/` (keys, Qdrant vectors, SQLite).
- **Model name:** the model string is currently duplicated in MANY places (llm.py, agent*.py,
  chat.py router response, metrics labels, logs). Phase 2 centralizes it; until then, keep them all
  in sync with `qwen/qwen3.8-27b`.
- **Rules for agents:** when a task spans multiple files, make one focused commit per concern,
  run lint + the matching smoke test, and update this file's roadmap (checked boxes) when done.

---

## 4. Execution Roadmap (in order)

### ⬜ Phase 1 — Commit & push current work — **DONE (bd7f638)** ✅
Deployment + observability phase committed and pushed.

### ⬜ Phase 2 — Make the LLM model configurable/switching-based
Problem: model name `qwen/qwen3.8-27b` is hardcoded in 21+ places across
`app/services/llm.py`, `app/services/agent.py`, `app/services/agent_graph.py`,
`app/services/agent_mcp.py`, `app/routers/chat.py`, `tools/run_eval.py`,
plus metrics/log label strings. Change it in one place and it should propagate.

Goal:
- Introduce a single config source (e.g. `app/config.py` or settings via env `LLM_MODEL`, with
  sensible default `qwen/qwen3.8-27b`).
- Replace hardcoded strings across services, routers, metrics labels, and judge model.
- Judge model in `tools/run_eval.py` should stay independently configurable (`EVAL_JUDGE_MODEL`),
  defaulting to the main model.
- `.env.example` documents the new vars.
- Verify: chat + agent + eval all run; metrics show the model label from config.

### ⬜ Phase 3 — Fix MCP in Docker + smaller correctness fixes
- **MCP in Docker broken:** Docker image ships only `app/` and has no `uv` in runtime stage;
  `agent_mcp.py` spawns `uv run python servers/documents.py` → fails in container.
  Options: copy `servers/`, `tools/`, `config/` (or just `servers/`) into the image; change
  the command to the venv python; ensure `.dockerignore` still excludes secrets/data.
- **Fix `app/dependencies.py:25`** — typo `WWW-Authenticated` → `WWW-Authenticate`.
- **Fix `app/routers/chat.py` `/chat/tools`** — `tool_used` should be `true` ONLY if a tool
  actually executed (currently always `true`).
- **Fix `chat.py` `/agent/graph`** — `stream` field present but silently ignored; either
  implement streaming or reject/ignore with a clear response (document which).
- **Non-streaming agents should also suppress reasoning/CoT** (same `extra_body` as chat).
- Each item ideally its own commit; or one smaller-fixes commit tracking the issue list.

### ⬜ Phase 4 — Create GitHub Issues for backlog (then address one-by-one in separate commits)
Backlog items (each becomes an issue, each fixed in its own commit):
1. **No automated tests** — only ruff + manual `tools/` scripts. Add pytest suite
   (unit: stores/keys/jobs/rate-limiter; integration: routers vs live stack).
2. **Model registry is a fake** — `models.py` uses hardcoded in-memory list unrelated to real
   inference; `POST /models` is lost on restart. Persist or remove.
3. **Content-hash dedup claimed but not enforced** — `worker.py` computes `content_hash` but
   `INSERT OR REPLACE` never checks it to skip duplicate content.
4. **Worker blocks event loop** — blocking `embed()` in async loop stalls all requests ~30s;
   use `asyncio.to_thread`. No job list/retry/heartbeat for stale `running` rows.
5. **MCP writes bypass metadata store** — MCP `add_document`/`delete_document` touch Qdrant only;
   they must sync SQLite metadata (visibility in `/documents/metadata`, purge via DELETE).
6. **Public SSRF risk** — `GET /fetch` (demo.py) proxies arbitrary URLs unauthenticated.
7. **Rate limiter is in-memory/per-process** — invalid with multiple uvicorn workers; needs
   shared store (Redis) or documented single-worker constraint.
8. **`calculate()` tool is `eval()`** — whitelist is small; assess/harden or remove.
9. **Cold-start embed model download** — sentence-transformer (~80MB) downloads on boot;
   pre-warm in image or fail fast with guidance.
10. **`.env` import-order risk** — routers import before `load_dotenv()` runs; break via
    `.env`-only key (see `main.py:11`).

### ⬜ Phase 5 — FIX the Phase-4 backlog issues (one issue per commit)
The issues created in Phase 4 ARE the work here. Before any production hardening, every
open issue from Phase 4 must be resolved:
- One focused commit per issue (they map 1:1 to GitHub issues; reference `closes #N`).
- Each commit runs `uv run ruff check app/` + the matching smoke test before done.
- Update this roadmap (checked boxes + issue links) as each issue lands.

### ⬜ Phase 6 — Production-ready hardening (after ALL Phase-4/5 backlog issues are fixed)
- CI/CD: extend `.github/workflows/lint.yml` → add build (docker build), tests, maybe deploy.
- Env hygiene: `.env.example` for everything; config docs; health/readiness split.
- Security: SSRF guard removed/fixed, secrets handling, dependency audit (uv audit).
- Docker: non-root already used; pin base images; healthcheck pass; trim image size.
- Scale concerns documented: single-worker rate limiting, Qdrant sizes, llm latency SLO.

### ⬜ Phase 7 — Replace PROGRESS.md / CONTINUATION.md with a narrative doc
Delete `PROGRESS.md` and `CONTINUATION.md`. Create a single `DOCS/` (or `THE-STORY.md`)
project document that:
- **Tells the story** — why the app exists, its ideology, how we built it phase-by-phase.
- **Best practices** applied (async IO, durable jobs, observability, OTel, auth/rate limits, SSE).
- **Known shortcomings + rationale** — explicitly say "we know X, we chose Y because it avoids
  over-engineering for this scale" (e.g. in-memory rate limiting, SQLite over Postgres,
  single uvicorn worker, no Redis/queue broker, model registry stub, demo endpoints).
- Update README links to point at the new doc (not PROGRESS/CONTINUATION).
- Cross-check: remove any stale references to PROGRESS.md/CONTINUATION.md everywhere.

---

## 5. Finished Work Index (for historical context until Phase 7)

- Topics 1–24 tracked in `PROGRESS.md` / `CONTINUATION.md` (will be deleted in Phase 7).
- Topics 25 (deployment), 26 (prod architecture), 27 (capstone) are untouched — they map to
  Phases 6/7 above.
- The Docker deploy phase (this work, commit `bd7f638`) made the full stack live, fixed
  Loki/Tempo healthchecks (static curl), otel-collector metrics, promtail config, OTLP tracing,
  and the Groq model rename. All 8 services verified healthy.