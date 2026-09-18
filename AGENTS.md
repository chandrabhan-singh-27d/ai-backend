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
- **Inference:** Groq, model default `qwen/qwen3.8-27b` — configurable via `LLM_MODEL` (Phase 2,
  done). Judge model independent via `EVAL_JUDGE_MODEL`.
- **Chrome-color note:** Docker image ships `app/` + `servers/` (MCP server); `.dockerignore`
  still excludes `tools/`, `config/`, secrets and `data/`.

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
  -d '{"id":"smoke-doc","text":"Qdrant is a vector database.","metadata":{"source":"smoke"}}'
curl -s http://localhost:8000/jobs/<job_id> -H "Authorization: Bearer <KEY>"

# RAG end-to-end
curl -s -X POST http://localhost:8000/rag \
  -H "Authorization: Bearer <KEY>" -H "Content-Type: application/json" \
  -d '{"question":"What is RAG?"}'
```

### Eval / tools
```bash
PYTHONPATH=. uv run python tools/run_eval.py          # RAG quality gate
API_KEY=<KEY> PYTHONPATH=. uv run python tools/stream_test.py   # SSE contract (needs an API key)
PYTHONPATH=. uv run python tools/test_agent_graph.py  # agent behavior
PYTHONPATH=. uv run python tools/mcp_client.py documents   # MCP server smoke
```

### Lint / typecheck / tests
```bash
uv run ruff check app/ tools/ servers/ tests/   # must be clean
uv run pyright app/services/job_store.py app/services/worker.py   # per-file only (whole repo is slow)
uv run pytest                                   # unit tests (hermetic); with the stack up:
#   AI_BACKEND_KEY=<KEY> uv run pytest          # includes live-stack integration tests
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
- **Model name:** the model string is centralized in `app/config.py` (`LLM_MODEL`, default
  `qwen/qwen3.8-27b`; eval judge `EVAL_JUDGE_MODEL`, default `openai/gpt-oss-120b`). Reasoning
  suppression is config-driven too (`LLM_REASONING_FORMAT`/`LLM_REASONING_EFFORT`,
  `EVAL_JUDGE_REASONING_EFFORT`). Do NOT hardcode model strings elsewhere.
- **Rules for agents:** when a task spans multiple files, make one focused commit per concern,
  run lint + the matching smoke test, and update this file's roadmap (checked boxes) when done.

---

## 4. Execution Roadmap (in order)

### ⬜ Phase 1 — Commit & push current work — **DONE (bd7f638)** ✅
Deployment + observability phase committed and pushed.

### ✅ Phase 2 — Make the LLM model configurable/switching-based — **DONE**
Problem: model name `qwen/qwen3.8-27b` was hardcoded in 21+ places across
`app/services/llm.py`, `app/services/agent.py`, `app/services/agent_graph.py`,
`app/services/agent_mcp.py`, `app/routers/chat.py`, `tools/run_eval.py`,
plus metrics/log label strings. Change it in one place and it should propagate.

Goal (all met):
- Single config source in `app/config.py` (`LLM_MODEL` env, sensible default `qwen/qwen3.8-27b`).
- Hardcoded strings replaced across services, routers, metrics labels, and judge model.
- Judge model in `tools/run_eval.py` stays independently configurable (`EVAL_JUDGE_MODEL`).
- `.env.example` documents the new vars.
- Verify: chat + agent + eval all run; metrics show the model label from config.

### ✅ Phase 3 — Fix MCP in Docker + smaller correctness fixes — **DONE**
All items fixed (commits `8ebca21` MCP-in-Docker, `b07802a` async embeds, `560dc25`
router correctness, `3cd1d90` auth/reasoning/rename, `713d4df`+`eca8974` MCP env,
`21c3a7b` eval fixes):
- **MCP in Docker fixed:** image now ships `servers/` and the agent spawns the venv python
  (`sys.executable`) — no `uv` needed; spawn env merges `os.environ` (MCP replaces it
  otherwise); `servers/documents.py` loads `.env` before app imports. `/agent/mcp`,
  `tools/mcp_client.py` verified against the Docker stack and locally.
- **`app/dependencies.py`** — `WWW-Authenticated` → `WWW-Authenticate` typo fixed.
- **`/chat/tools`** — `tool_used` is `true` only when a tool actually executed
  (`chat()` returns `(content, tool_used)`).
- **`/agent/graph`** — `stream=true` is rejected with a clear 400 (streaming not
  implemented for graph); `max_tokens` is honored; `GraphRecursionError` returns a
  message instead of a 500.
- **Reasoning/CoT suppressed everywhere** via config (`LLM_REASONING_*`), including
  non-streaming agents and the eval judge (`EVAL_JUDGE_REASONING_EFFORT=low` — gpt-oss
  accepts only low/medium/high).
- Bonus fixes from audit: `embed_sync()` removed from all async wait paths (async
  `call_tool` dispatcher), `max_tokens` plumbing to `/agent`, `/agent/mcp`,
  `chat_stream` default and tool-round final call, SSE error frames on streaming
  endpoints (was silent connection drop), streamed tools path now yields direct text
  answers, `EmbedRequst` → `EmbedRequest`, `tools/stream_test.py` sends the API key,
  `tools/run_eval.py` loads `.env` before app imports.

### ✅ Phase 4 — Create GitHub Issues for backlog — **DONE**
Issues created on `chandrabhan-singh-27d/ai-backend`: #8, #9, #10, #11, #12, #13, #14, #15, #16
(item #9 below — cold-start embed download — was resolved by the HF Inference Providers swap,
so no issue was created for it). Each fixed in its own commit in Phase 5:

1. **No automated tests** — only ruff + manual `tools/` scripts. Add pytest suite
   (unit: stores/keys/jobs/rate-limiter; integration: routers vs live stack). → **issue #8**,
   **blocks production deployment (must be fixed before Phase 6).**
2. **Model registry is a fake** — `models.py` uses hardcoded in-memory list unrelated to real
   inference; `POST /models` is lost on restart. Persist or remove. → **issue #9**
3. **Content-hash dedup claimed but not enforced** — `worker.py` computes `content_hash` but
   `INSERT OR REPLACE` never checks it to skip duplicate content. → **issue #10**
4. **Worker blocks event loop** — blocking `embed()` in async loop stalls all requests ~30s;
   use `asyncio.to_thread`. No job list/retry/heartbeat for stale `running` rows. → **issue #11**
5. **MCP writes bypass metadata store** — MCP `add_document`/`delete_document` touch Qdrant only;
   they must sync SQLite metadata (visibility in `/documents/metadata`, purge via DELETE). → **issue #12**
6. **Public SSRF risk** — `GET /fetch` (demo.py) proxies arbitrary URLs unauthenticated. → **issue #13**
7. **Rate limiter is in-memory/per-process** — invalid with multiple uvicorn workers; needs
   shared store (Redis) or documented single-worker constraint. → **issue #14**
8. **`calculate()` tool is `eval()`** — whitelist is small; assess/harden or remove. → **issue #15**
9. **Cold-start embed model download** — sentence-transformer (~80MB) downloads on boot;
   pre-warm in image or fail fast with guidance. ✅ **Resolved by design:** embeddings moved
   to Hugging Face Inference Providers (commit `2737e9c`) — no local model/download at all.
10. **`.env` import-order risk** — routers import before `load_dotenv()` runs; break via
    `.env`-only key (see `main.py:11`). → **issue #16**

### ✅ Phase 5 — FIX the Phase-4 backlog issues (one issue per commit) — **DONE**
All 9 backlog issues closed, each in its own focused commit (ruff + smoke per commit):
- ✅ **#8 automated tests** — `acb22e8` (pytest suite: unit stores/keys/jobs/rate-limiter/
  vector/metadata/worker/ssrf/tools/mcp-server + live integration; 51 hermetic unit tests).
- ✅ **#9 model registry persisted** — `5e5bb88` (SQLite ModelStore seeded from
  `LLM_MODEL`/`EVAL_JUDGE_MODEL`; survives restart).
- ✅ **#10 content-hash dedup enforced** — `1ed04c6` (`find_by_content_hash` → skip
  embed/vector; job result `duplicate` + `deduped_against`).
- ✅ **#11 worker async + retry + heartbeat + job list** — `69ec133`
  (`asyncio.to_thread` for qdrant writes, attempts w/ `JOB_MAX_ATTEMPTS` requeue,
  stale-row reclaim w/ `JOB_HEARTBEAT_TIMEOUT_SECONDS`, `GET /jobs`).
- ✅ **#12 MCP writes sync metadata** — `631cdba` (add/delete → SQLite rows).
- ✅ **#13 SSRF /fetch** — `72c4d88` (authenticated + `validate_fetch_url` private-range
  guard; `/slow-*` public demo endpoints were later gated behind `DEMO_ENDPOINTS` in Phase 6).
- ✅ **#14 rate limiter strategy** — `3983558` (`RateLimiter` ABC: `MemoryRateLimiter`
  default/single-worker, `RedisRateLimiter` fixed-window for multi-worker via
  `RATE_LIMIT_STRATEGY`/`REDIS_URL`; compose pins memory + documents the constraint).
- ✅ **#15 calculate() hardened** — `de2e208` (eval → whitelist AST evaluator).
- ✅ **#16 .env import order** — `528189d` (`load_dotenv()` before app imports).

The Docker image was rebuilt by the user (17:35) and the full verify + live integration
suite re-ran green on the new image (60/60; store restored to pristine state afterwards).

### ✅ Phase 6 — Production-ready hardening — **DONE** (`007bdb1`, `4dc3157`, `5f116f0`, `22373f0`, `81bc17a`)
- ✅ **CI/CD** — `007bdb1`: workflow extended from lint-only to `CI` (ruff, pyright,
  52 hermetic unit tests, and a `docker build` job per push).
- ✅ **Env hygiene** — `4dc3157`: `.env.example` documents every var
  (`GROQ_API_KEY`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES`, `MODELS_DB_PATH`,
  `JOB_MAX_ATTEMPTS`/`JOB_HEARTBEAT_TIMEOUT_SECONDS`, `DEMO_ENDPOINTS`); env reads
  centralized in `app/config.py` (tracing.py no longer reads env directly).
- ✅ **Health/readiness split** — `5f116f0`: `/health` liveness probe stays trivial;
  `/health/ready` checks Qdrant + SQLite and returns 503 until usable.
- ✅ **Security** — `81bc17a`: pyright strict CI fixed (all 20 errors in
  llm/tools/ssrf/rate_limiter). `ab4e789`: SSRF IPv4-mapped-IPv6 bypass closed
  (`::ffff:127.0.0.1`); `uv audit` clean — httpx2 raised 2.10.0 → 2.13.0 (6 CVEs),
  unused `anthropic` pin dropped. `5f116f0`: friendly `GROQ_API_KEY` startup error,
  config-driven LLM timeout/retries, demo `/slow-*` endpoints gated behind
  `DEMO_ENDPOINTS` (default off; `/slow-blocked` was a public event-loop DoS).
- ✅ **Docker** — `22373f0`: every image pinned to a proven tag (qdrant v1.19.1,
  otel-collector-contrib 0.161.0, prometheus v3.14.0, tempo 2.10.8, loki 3.7.8,
  promtail 3.6.11, grafana 13.2.2, base `python:3.14.7-slim`) + `restart:
  unless-stopped` on all services. Non-root user and healthchecks already in place.
- Scale concerns (single-worker rate limiting, Qdrant sizes, LLM latency SLO) are
  documented in `THE-STORY.md` (Phase 7).

### ✅ Phase 7 — Replace PROGRESS.md / CONTINUATION.md with a narrative doc — **DONE**
- Deleted `PROGRESS.md` and `CONTINUATION.md`, created a single `THE-STORY.md` project
  document that:
  - **Tells the story** — why the app exists, its ideology (guided discovery,
    incremental complexity, explain-the-why), how it was built phase-by-phase.
  - **Best practices** applied (async IO, durable jobs, observability, OTel,
    auth/rate limits, SSE, deterministic IDs, strict typing gates).
  - **Known shortcomings + rationale** — an explicit table of tradeoffs ("we know X,
    we chose Y because it avoids over-engineering for this scale": in-memory rate
    limiting, SQLite over Postgres, single uvicorn worker, no Redis/queue broker,
    model registry stub, demo endpoints) plus concrete scale concerns (Qdrant sizing,
    LLM latency SLO, job retry backoff).
  - README rewritten: links point at `THE-STORY.md` (not PROGRESS/CONTINUATION),
    auth/API-key docs, complete endpoint table, correct run commands, pinned-image
    notes. Cross-checked: no stale PROGRESS/CONTINUATION references remain (only
    historical mentions in this roadmap).

---

## 5. Finished Work Index (for historical context)

- Topics 1–24 were tracked in `PROGRESS.md` / `CONTINUATION.md` (deleted in Phase 7);
  the full phase-by-phase story, best practices, tradeoffs, and scale concerns now live
  in `THE-STORY.md`.
- Topics 25 (deployment) and 26 (prod architecture) map to Phases 6/7 above and are
  complete; Topic 27 (capstone) is the next challenge.
- The Docker deploy phase (`bd7f638`) made the full stack live, fixed
  Loki/Tempo healthchecks (static curl), otel-collector metrics, promtail config, OTLP tracing,
  and the Groq model rename. All 8 services verified healthy.