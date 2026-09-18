# THE STORY — why AI Backend exists and how it was built

This project started as a teaching exercise: build a "production-grade" RAG + agent
backend **one small topic at a time**, with a human writing every line of code and an
AI tutor explaining the *why* behind each choice. It ended up as a real, deployable
system — a FastAPI service with a background worker, a vector database, an LLM-agent
loop, MCP tool servers, and a full observability stack — running in Docker.

This document is the story of that journey: the ideology, the phases, the best
practices we deliberately applied, and — just as important — the tradeoffs we made on
purpose, with the reasons.

---

## 1. The ideology

- **Incremental complexity.** Every topic (27 of them) builds on the previous one.
  The app didn't start as an architecture diagram; it started as a `hello world` route
  and grew into the current structure one commit at a time.
- **No dumping solutions.** The tutor gives hints first, reviews like a staff
  engineer, and keeps the developer in the "struggle zone" so the lessons stick.
  The code is written by a human, not generated wholesale.
- **Explain the "why".** Choices in this repo carry a rationale, not just an
  implementation. Where a shortcut was taken, it's a deliberate shortcut — see §5.
- **Correctness gates from day one.** Ruff (E/F/I/UP/B/SIM/RUF), pyright **strict**
  mode, and — later — a real pytest suite run in CI on every push. Type errors and
  lint violations are never allowed to accumulate.

## 2. How we built it, phase by phase

### Phase 1 — Foundations (Topics 1–8)
Flat `app/` package, uv for dependency management, FastAPI with a composition root
(`app/main.py` owns app construction + router registration). Pydantic for request
validation, `TypedDict` for internal shapes. Async from the start: `async def` vs
`def`, the event loop, threadpool semantics. `httpx.AsyncClient` for outbound calls
and the OpenAI SDK pointed at Groq's OpenAI-compatible API. Embeddings moved from
`all-MiniLM-L6-v2` on `sentence-transformers` to the **Hugging Face Inference
Providers** API — no 80MB model download in the image at all (Phase-4 backlog item #9).

### Phase 2 — Core AI patterns (Topics 9–13)
Vector search (in-memory first, then Qdrant), then **RAG**: retrieve → augment →
generate with context injection. OpenAI **function calling** with a whitelisted tool
set (`calculate`, `search_documents`, `list_documents`), then the **Model Context
Protocol**: a standalone `servers/documents.py` MCP server speaking stdio, with the
agent as an MCP client. Finally, AI agents: an LLM loop that autonomously decides to
call tools.

### Phase 3 — Production readiness (Topics 14–24)
LangGraph for a graph-based agent, LLM-as-judge **evaluation** with rubric scoring and
golden fixtures, then the meaty part:

- **Observability**: structured JSON logs with request/trace correlation, Prometheus
  metrics (HTTP, LLM latency, tokens, TTFT), OpenTelemetry spans, and a full
  Grafana/Loki/Tempo/Prometheus stack in Docker with provisioned dashboards and an
  SLO recording rule (`ai_backend:error_ratio:5m`).
- **Durability**: Qdrant as the persistent vector store with deterministic UUID5
  point IDs; SQLite stores (metadata, jobs, API keys, model registry) with WAL and
  parameterized queries.
- **Streaming SSE**: token/tool/done frames over Server-Sent Events with
  time-to-first-token telemetry.
- **Auth**: bearer API keys stored as **SHA-256 hashes only** (never plaintext),
  per-key rate limiting, a management CLI (`tools/manage_keys.py`).
- **Background jobs**: a durable SQLite job queue with a worker loop — `202 accepted`
  + poll, attempts/requeue, stale-row reclaim, heartbeat timeouts.

Then a Docker deploy phase stamped the whole thing live: 8 services
(app, qdrant, otel-collector, tempo, prometheus, loki, promtail, grafana), healthchecks
everywhere, and Host-side uv cache mounts so rebuilds don't re-download the dependency
tree.

### Phase 4–6 — Backlog, hardening, and production hygiene
Nine real-world issues surfaced in a staff-level audit and were turned into GitHub
issues (#8–#16), each fixed in its own focused commit:

- The **test suite** that was missing from day one (`#8`).
- The fake in-memory model registry, now a persisted SQLite store seeded from config (`#9`).
- Content-hash **dedup** that was claimed but not enforced (`#10`).
- A worker that **blocked the event loop**, now `asyncio.to_thread` + retries (`#11`).
- MCP writes that bypassed the metadata store, now synced (`#12`).
- An **unauthenticated SSRF** `/fetch`, now protected + private-range-guarded (`#13`).
- An in-memory-only rate limiter, now an ABC with a Redis option (`#14`).
- A `calculate()` tool built on `eval()`, now a whitelist AST evaluator (`#15`).
- An `.env` import-order landmine (`#16`).

Phase 6 then hardened the ops surface: CI with tests + docker build, a complete
`.env.example`, a `/health/ready` split, an SSRF IPv4-mapped-IPv6 bypass fix, a clean
`uv audit`, pinned container tags, restart policies, and demo endpoints gated behind
`DEMO_ENDPOINTS`.

## 3. Best practices deliberately applied

- **Service modules over fat routers.** Business logic lives in `app/services/`;
  routers stay thin transports.
- **Composition root.** `app/main.py` is the only place that wires the app together.
- **Async I/O everywhere it matters** — with `asyncio.to_thread` for blocking Qdrant
  writes so the event loop never stalls (and the `/slow-blocked` endpoint exists
  purely to demonstrate why that discipline matters).
- **Durable, observable background work** — jobs survive restarts, retries are
  bounded (`JOB_MAX_ATTEMPTS`), stale `running` rows get reclaimed, and every job
  state transition is visible via `GET /jobs`.
- **Observability by default** — every request gets a request ID echoed back in
  `X-Request-Id`; every log line carries request/trace/span IDs; metrics are
  label-driven (`model`, `segment`, `status`) so dashboards can slice any axis.
- **Secrets handling** — keys hashed at rest, `.env` never committed, `.dockerignore`
  excludes everything sensitive, and the app fails fast with a readable message if
  `GROQ_API_KEY` is missing.
- **Deterministic identity** — Qdrant point IDs are UUID5 derived from the document
  ID, so re-ingestion is idempotent (and content-hash dedup skips duplicate text
  entirely).
- **Strict typing + lint gates** — pyright `strict` over `app/` + `servers/`, enforced
  in CI, per the repo conventions.
- **Evaluation as a gate** — `tools/run_eval.py` scores retrieval and faithfulness
  with an independent judge model, so "it works" is a measured claim, not a vibe.

## 4. Architecture at a glance

```
Request ── FastAPI (routers) ── services ── Qdrant (vectors)
                                │           SQLite (metadata / jobs / keys / models)
                                ├── Groq (LLM, OpenAI SDK)
                                ├── HF Inference (embeddings)
                                ├── MCP stdio server (tools)
                                └── worker loop (durable async jobs)

Observability: Prometheus metrics, OTel spans → collector → Tempo,
JSON logs → Loki (via promtail); Grafana dashboards + alerting rules.
```

## 5. Known shortcomings and the rationale (we know, and we chose)

This section is the honest part. Each of these is a *known* limitation; for each we
can name the scale at which it starts hurting and what we'd swap in.

| Shortcoming | Why it's fine today | When to fix it |
|---|---|---|
| **Rate limiting is in-process** (`MemoryRateLimiter`) | Valid for a single uvicorn worker; the constraint is documented and CI-pinned | The moment you run ≥2 workers, set `RATE_LIMIT_STRATEGY=redis` |
| **SQLite instead of Postgres** | Perfectly durable, zero-ops, WAL mode; the API+worker write volume is tiny | >1M rows or concurrent multi-process writers |
| **Single uvicorn worker** | Async + a background worker thread is the whole concurrency model; keeps the in-memory limiter valid | Under real traffic, scale out with Redis limiter + multiple workers |
| **No message broker (Redis queue)** | SQLite polling with 0.5s interval is instant for our job volume and trivially inspectable | When jobs need fan-out, priorities, or sub-second SLA |
| **Model registry is a metadata stub** | It persists models from config and documents what's available; inference names stay centralized in `app/config.py` | When you need dynamic model routing or per-key model policies |
| **`/fetch` is a minimal HTTP proxy** | Authenticated + SSRF-guarded; no redirects, 10s timeout | When you need caching, size caps, or a real URL-fetch service |
| **Demo `/slow-*` endpoints** | Off by default (`DEMO_ENDPOINTS=false`); they exist to teach event-loop behavior | Delete them whenever the teaching is done |
| **SHA-256-hashed API keys** | Keys are 128-bit random, so brute-force is impractical; hashing prevents DB-leak plaintext exposure | If keys ever become derivable/leaked at scale, move to argon2 |
| **Embeddings are sequential per text** | HF Inference is fast and call volume is low | Batch requests and add retry/backoff when volume grows |
| **LangGraph graph compiled per request** | Compilation is cheap; keeps the code simple | Cache compiled graphs when request rates grow |
| **Grafana admin password is a dev default** | The stack binds to localhost; anonymous read access is intentional for demos | Lock down auth + secrets for any exposed deployment |

### Scale concerns (the "production" numbers)

- **Qdrant sizing**: all vectors are 384-dim and stored in one collection; payload
  holds the full text. Watch `qdrant_storage/` growth and set an HNSW `ef_construct`
  tuned to your recall/latency needs at scale.
- **LLM latency SLO**: end-to-end latency is dominated by Groq round-trips
  (non-stream chat/tool rounds). The `llm_latency_seconds` and
  `llm_time_to_first_token_seconds` histograms plus the `ai_backend:error_ratio:5m`
  recording rule are the SLO surface — alert on those, not on host metrics.
- **Job queue**: a crashed worker mid-job is handled (stale reclaim), but jobs are
  not retried with backoff — a permanently failing job retries back-to-back until
  `JOB_MAX_ATTEMPTS`. Fine at this scale; add exponential backoff before heavy use.

## 6. Where the code lives

- `app/` — FastAPI app: `main.py` (composition root), `routers/`, `services/`,
  `middlewares/`.
- `servers/documents.py` — MCP tool server (stdio).
- `tools/` — CLI scripts: key management, eval, SSE contract test, MCP client,
  agent-graph test.
- `config/` — Docker/observability configs (otel-collector, prometheus, loki,
  promtail, tempo, grafana provisioning).
- `data/` — SQLite databases + Qdrant storage (bind-mounted, survive everything
  except `docker compose down -v`).
- `.github/workflows/lint.yml` — CI: ruff, pyright strict, 52 hermetic unit tests,
  docker build.

The operational facts (how to run, verify, and extend) live in `AGENTS.md`; this file
is the *why*.