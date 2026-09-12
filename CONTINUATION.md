# Continuation Prompt for AI Backend Project

## Project Overview
Building a production-grade AI backend incrementally with Python/FastAPI/Groq. Project at `/home/chandrabhan/project/ai-backend`. Teaching style: guided discovery, no dumping solutions, Staff Engineer code review, keep developer stuck as long as possible.

## User Profile
- Experienced JS/TS backend engineer (~5 years), no Python/AI background
- Types all code manually, tutor explains problems and reviews
- Shell: zsh with powerlevel10k, VSCode with Ruff + Pylance
- Python 3.14, pyright strict mode, Ruff rules `["E", "F", "I", "UP", "B", "SIM", "RUF"]`, line-length 100
- LLM: Groq (GROQ_API_KEY), no OpenAI/Anthropic keys

## What's Built (Topics 1-19 ✅)

### Foundations
1. **Project structure** — flat layout, `app/` package, pyproject.toml
2. **venv/deps** — uv venv, uv.lock, .gitignore
3. **FastAPI** — routers, composition root, include_router
4. **Pydantic** — BaseModel (requests), TypedDict (internal shapes), 422 responses
5. **Async** — async def vs def, event loop, threadpool blocking demo
6. **HTTP clients** — httpx AsyncClient, async context managers
7. **LLM SDKs** — OpenAI SDK with Groq base_url, service layer pattern
8. **Embeddings** — sentence-transformers all-MiniLM-L6-v2, cosine similarity

### Core AI Patterns
9. **Vector DB** — in-memory store with TypedDict (Document, ScoredDocument), cosine search
10. **RAG** — retrieve → augment → generate, `/rag` endpoint
11. **Tool calling** — OpenAI function calling, ChatCompletionToolParam, TOOL_MAP, tools_enabled param
12. **MCP** — MCP 2.0 callback API (Server, on_list_tools, on_call_tool), stdio transport, documents server in `servers/documents.py`
13. **AI Agents** — two implementations:
    - Direct: `app/services/agent.py` (tools hardcoded in llm.py)
    - MCP: `app/services/agent_mcp.py` (discovers tools from MCP server at runtime)
14. **Agent Frameworks (LangGraph)** — `app/services/agent_graph.py`:
    - `AgentState(TypedDict)` with `messages: Annotated[list[dict[str, object]], operator.add]` (reducer = append-not-replace)
    - Two nodes: `call_llm` (returns assistant msg delta), `run_tools` (parses plain dicts from state via `cast`, executes TOOL_MAP)
    - Router `route_after_llm` returns `"run_tools"` or `END` based on `"tool_calls" in last_message`
    - Graph wired with 3 edges: START→call_llm, call_llm→(conditional), run_tools→call_llm; compiled at module level
    - Runner `run_agent_graph(question)` uses `await graph.ainvoke(..., config={"recursion_limit": 10})` (recursion_limit ≈ old max_steps)
    - Served at POST `/agent/graph` in chat.py; verified end-to-end vs hand-rolled agent (both answer sqrt(144)=12)
15. **Evaluation** — `tools/run_eval.py` harness:
    - Golden fixtures in `tools/eval_cases.json` (4 answerable + 1 unanswerable refusal case); seed corpus in `tools/corpus.json`
    - Idempotent in-process seeding (fixed IDs overwrite via store dict); suite works cold, no server needed
    - Layered grading: retrieval check (`expected_doc_ids ⊆ top-3`, pure set math) vs answer quality (LLM judge)
    - Judge = same Groq model (`qwen/qwen3.6-27b`), dedicated AsyncOpenAI client, temperature=0; rubric prompts anchored on CONTEXT (faithfulness, not world knowledge); inverted rubric for unanswerable cases
    - Verdict = Pydantic `JudgeVerdict(score: int = Field(ge=1, le=5), reasoning)`
    - Defensive parse pipeline survived live failures: `<think>` strip → skip to first `{` → `raw_decode` first JSON value → array-unwrap via cast loop → Pydantic validate
    - Suite gate: all-retrieval AND min score ≥ 3 AND avg ≥ 4.0 → `sys.exit(0/1)` for CI
    - Status: PASS — 5/5 retrieval, avg 4.60/5, min 4/5
16. **Observability** — logging + tracing + monitoring:
    - **Tracing**: `RequestContext` dataclass + `ContextVar` in `app/services/context.py`; middleware mints `request_id` (uuid4), captures sanitized client `X-Request-Id` as `client_id`; `Token`-based reset prevents stale context leaking into background tasks/threads; backend ID echoed as `X-Request-Id` response header
    - **Logging**: `JSONFormatter` in `app/services/logging.py` emits one-line JSON with `request_id`/`client_id` on every logger (incl. httpx); `setup_logging()` wired in main; app logs at middleware (request lifecycle), llm (`llm_call`), rag (`rag_retrieval`), chat router (error paths)
    - **Monitoring**: `prometheus-client` in `app/services/metrics.py` + `/metrics` route; `llm_latency_seconds` Histogram (labels model/tools_enabled/segment: tool_round/final/agent_round/agent_graph/agent_mcp), `llm_tokens_total` Counter, `http_requests_total` Counter + `http_request_duration_seconds` Histogram (labels method/path/status; path uses `scope["route"].path` to avoid cardinality explosion; `/metrics` excluded)
    - `measure_llm_call()` context manager wraps every LLM call (plain chat + all three agents) for timing + token counting

### Persistence Phase (Topics 17-18 ✅)
17. **Qdrant Vector DB** — `app/services/vector_store.py` rewritten as Qdrant-backed `VectorStore` class:
    - Instance state = client/collection/vector_size; idempotent `create_collection(Distance.COSINE)` on init
    - Deterministic point ID `str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))` → upsert overwrites → idempotent re-seed; business `doc_id` kept in payload
    - Methods mirror old interface: add/search/delete/get/exists/count/list_all; `get_store()` lazy singleton (localhost:6333, 384-dim)
    - Rewired callers: documents router, rag.py (`store` param on answer_question), llm.py tools, MCP documents server, run_eval (isolated in-memory `EVAL_STORE`)
    - Docker: `qdrant/qdrant` 1.19, ports 6333/6334, volume `qdrant_storage/` (gitignored)
    - Eval gate green: 5/5 retrieval, avg 4.60/5, min 4/5
    - Groq OTPM 429 fix: explicit `max_tokens` + `extra_body={"reasoning_format": "hidden", "reasoning_effort": "none"}` on all chat() calls + judge → completion ~14 tokens vs ~290
18. **Database Persistence** — `app/services/metadata_store.py` SQLite store + durable JSON logs:
    - `MetadataStore(db_path="data/app.db")`: `documents` table (doc_id PK, title, source, content_hash, chunk_count, created_at); WAL via PRAGMA; `row_factory=sqlite3.Row`; per-call connections (thread-safety, auto-commit via `with`)
    - `INSERT OR REPLACE` upsert = idempotent re-ingest; `?` parameterized queries everywhere
    - `logging.py`: `TimedRotatingFileHandler("logs/app.log", when="midnight", backupCount=7, encoding="utf-8")` + console, same JSONFormatter
    - Documents router: ingest records metadata (title fallback `request.title or request.id`, sha256 content_hash, chunk_count=1), `GET /documents/metadata`, delete purges both stores
    - Verified in-process round-trip; Qdrant + SQLite both empty after delete

### Observability Phase (Topic 19 ✅)
19. **OpenTelemetry Integration** — `app/services/tracing.py` + instrumentation:
    - `setup_tracing()`: TracerProvider with `Resource({"service.name": "ai-backend"})`, `SimpleSpanProcessor(ConsoleSpanExporter())` (Phase 19 visibility; Phase 20 → OTLP to Collector)
    - `get_tracer()` re-resolves the provider per call — avoids the Tracer-welded-to-import-time-NoOp trap
    - `main.py`: `setup_tracing()` before `FastAPIInstrumentor.instrument_app(app)` → HTTP root span per request; `# pyright: reportMissingTypeStubs=false` (untyped instrumentation package, same pattern as agent_graph.py)
    - `rag.py`: spans answer_question → {embedding, store.search, build_prompt}
    - `metrics.py` measure_llm_call: `llm_call.{segment}` span — single chokepoint traces every LLM call
    - `logging.py` JSONFormatter: `trace_id` (032x) / `span_id` (016x) injected when the active span is valid
    - Proven in-process (zero Docker): shared trace_id across the tree; siblings share parent_id; rag_retrieval log carries its parent span_id + trace_id
20. **Observability Stack (Docker)** — `docker-compose.yml` + `config/`:
    - 7 services: qdrant, otel-collector (OTLP ingress 4317/4318, debug + forward to `tempo:4317`), tempo (3200), prometheus (`host.docker.internal:8000` via host-gateway + collector 8888), loki (3100), promtail (tails `logs/app.log*`; json stage promotes trace_id/span_id/level → labels), grafana (3000, auto-provisioned datasources)
    - Readiness gating: `depends_on: {service: healthy}` chains collector→tempo and promtail→loki; bare depends_on = start-order only
    - Parse-validated only; container run deferred to final assembly
21. **Monitoring Dashboards** — SLOs + triage dashboard + alert rules:
    - SLOs (user-chosen): success ≥ 95%; latency p95 < 15s (loosened from 5s — agent tool loops stack multiple LLM calls)
    - Recording rules `config/prometheus/rules.yml`: `ai_backend:error_ratio:5m`, `ai_backend:success_ratio:5m`
    - `config/grafana/provisioning/dashboards/rag-overview.json`: ER-triage layout — Vitals (error-ratio stat, req/s, p95 HTTP w/ 15s threshold) → Diagnostics (LLM p95 overall + by segment, token rate) → Deep-dive (4xx/5xx, Loki error logs `{job="ai-backend"} | json | level = "error"`)
    - Grafana alert rules (provisioned in `config/grafana/provisioning/alerting/rules.yml`): high error burn (>0.06 ratio → page), slow LLM (p95 > 15s → warning); alerts evaluate the recording rule / p95 query
22. **Streaming SSE + TTFT**:
    - Opt-in `stream: bool = False` on `/chat`, `/chat/tools`, `/agent` request models; when true → `text/event-stream` (SSE `data: {…}\n\n` frames via FastAPI `StreamingResponse` + `_frame` helper in `app/routers/chat.py`)
    - Event contract: `{"type": "token", "content"}` | `{"type": "tool_call", "name"}` | `{"type": "done"}`; non-stream paths untouched
    - `chat_stream()` in `app/services/llm.py` (tool loop + final pass), `run_agent_stream()` in `app/services/agent.py` (multi-round); `iter_chunks()` + `log_llm_usage()` shared helpers
    - Configurable response length: `max_tokens: int = 400` on chat(), chat_stream(), run_agent(), run_agent_stream(), threaded from request `max_tokens` field
    - TTFT: `llm_time_to_first_token_seconds` Histogram (LLM_TTFT, labels model/segment) recorded at first content token in streaming paths
    - `tools/stream_test.py`: in-process ASGITransport SSE test, verified against real Groq
    - **pyright root-cause fix**: tools-path streaming errors came from `messages: list[dict[str, object]]` breaking SDK overload resolution (→ Unknown return). Fix = type `messages: list[ChatCompletionMessageParam]` from `openai.types.chat` — removed all `# type: ignore[arg-type]`, no pragmas/casts
23. **Auth & API Keys**:
    - `app/services/api_keys.py` — `ApiKeysStore` in its own DB (`data/keys.db`, WAL, per-call connections). Keys are `ak_live_<32 hex>`; only their **SHA-256 hash** is stored (same dedup mind-set as content_hash). `create(name)` returns the full key exactly once; `find(input)` hashes-and-matches and excludes `revoked=1`; `revoke()` keeps the row (audit history); `list_all()` returns `fingerprint = substr(key_hash,1,8)` so you can identify keys without a leak vector
    - `app/dependencies.py` — `HTTPBearer(auto_error=False)` (default raises 403 — wrong code; we want 401 both missing and invalid with `WWW-Authenticate: Bearer`). `Annotated[HTTPAuthorizationCredentials | None, Depends(...)]` alias avoids Ruff **B008** (function call in argument default). `require_api_key` stores the key row on `request.state.api_key`; `require_rate_limit` → **429**
    - `app/services/rate_limiter.py` — sliding-window per key: `deque[float]` of `time.monotonic()` timestamps, prune-with-while, count in window; `PROTECTED = [Depends(require_api_key), Depends(require_rate_limit)]`
    - Routers `chat`, `documents`, `embeddings`, `rag` → `APIRouter(dependencies=PROTECTED)`; `/health` + `/metrics` stay public. Dependency rejection precedes the handler → unauthenticated `/redis`-expensive calls never cold-load the embedding model
    - `tools/manage_keys.py` — argparse subcommand CLI (`create NAME` / `list` / `revoke KEY_ID`), `set_defaults(func=...)` dispatch
    - `auth_failures_total` Counter, labels `reason`: `missing_key` / `invalid_key` / `rate_limited`
    - Verified live: 401/401/200 matrix, 58×200→429 hammer (bucket is per-key across all endpoints), metrics grep `missing_key=1, invalid_key=2`

### Key Files
- `app/main.py` — mounts 6 routers (health, models, demo, chat, embeddings, documents, rag)
- `app/services/llm.py` — AsyncOpenAI + Groq, TOOLS (ChatCompletionToolParam), TOOL_MAP, chat() with tools_enabled; qwen reasoning hidden via `reasoning_format` extra_body + `_strip_reasoning` fallback
- `app/services/embeddings.py` — SentenceTransformer, embed(), cosine_similarity()
- `app/services/vector_store.py` — Qdrant-backed VectorStore + get_store() lazy singleton
- `app/services/metadata_store.py` — SQLite MetadataStore + get_metadata_store() lazy singleton (WAL, per-call connections)
- `app/services/tools.py` — calculate() with eval whitelist
- `app/services/rag.py` — build_prompt(), answer_question(question, store=None)
- `app/services/agent.py` — run_agent() with tool loop
- `app/services/agent_graph.py` — LangGraph agent (AgentState, call_llm, run_tools, route_after_llm, graph, run_agent_graph)
- `app/services/agent_mcp.py` — run_mcp_agent() connecting to MCP server
- `app/services/context.py` — RequestContext dataclass, ContextVar, token-based set/reset
- `app/services/logging.py` — JSONFormatter (request-scoped + trace_id/span_id fields) + setup_logging (console + TimedRotatingFileHandler to logs/)
- `app/services/tracing.py` — setup_tracing (TracerProvider/Resource/ConsoleSpanExporter) + get_tracer (lazy, per-call)
- `app/services/metrics.py` — Prometheus metrics (LLM latency/tokens/TTFT, HTTP count/duration, auth failures) + measure_llm_call (also opens llm_call.{segment} span)
- `app/services/api_keys.py` — ApiKeysStore (hash-only storage) + generate/hash utils
- `app/services/rate_limiter.py` — sliding-window per-key limiter (in-memory)
- `app/dependencies.py` — require_api_key + require_rate_limit + PROTECTED dependency list
- `app/middlewares/request_context.py` — request_id/client_id middleware + HTTP metrics
- `app/routers/metrics.py` — GET /metrics scrape endpoint
- `servers/documents.py` — MCP 2.0 server (list_tools, call_tool callbacks)
- `tools/mcp_client.py` — MCPTestClient with DocumentsTest class
- `tools/test_agent_graph.py` — side-by-side hand-rolled vs langgraph agent test
- `tools/eval_cases.json` — golden eval cases (questions, expected_doc_ids, expected_facts, answerable flag)
- `tools/corpus.json` — seed documents so the eval suite is self-contained
- `tools/run_eval.py` — eval harness (seed → retrieval check → generate → judge → report → exit code)
- `tools/manage_keys.py` — API key CLI (create / list / revoke)
- `app/routers/chat.py` — /chat, /chat/tools, /agent, /agent/mcp, /agent/graph (all three main endpoints support opt-in SSE streaming + max_tokens)
- `tools/stream_test.py` — in-process SSE stream test (/chat, /chat/tools, /agent)
- `app/routers/documents.py` — /documents, /search, /documents/metadata, /documents/{id}
- `docker-compose.yml` — INITIAL (not yet run): Qdrant, OTel Collector, Prometheus, Loki, Tempo, Grafana
- `config/otel-collector/`, `config/prometheus/` (incl. rules.yml), `config/grafana/` (datasources, dashboards/, alerting/), `config/loki/`, `config/tempo/`, `config/promtail/` — INITIAL (not yet run)

### Key Design Decisions
- Pydantic for API validation, TypedDict for internal types
- SentenceTransformer imports inside functions (lazy loading, heavy model)
- `# type: ignore` only when SDK types genuinely can't resolve (OpenAI union types, sentence-transformers)
- `assert isinstance()` for type narrowing over cast — EXCEPT container contents: `cast("dict[str, object]", x)` when shape hides inside a list/dict, since isinstance can't check generics
- File-scoped `# pyright: reportUnknownMemberType=false, reportMissingTypeStubs=false` at top of agent_graph.py for langgraph's incomplete types
- Graph state holds raw OpenAI-style dicts; once serialized to dicts, downstream nodes must treat them as dicts (no SDK-class isinstance checks on state data)
- Reducer (`operator.add`) makes node deltas append to messages instead of replacing them
- `store` not `_store` in vector_store.py (needs external import from MCP server)
- `anyio.run()` for MCP servers, not `asyncio.run()` (MCP SDK uses anyio internally)
- Two agent patterns: direct (simple) vs MCP (decoupled, dynamic tool discovery); third = LangGraph (declared topology, framework-owned loop)
- Eval judge: separate AsyncOpenAI client with temperature=0 — eval knobs never leak into prod `chat()`
- Extraction-based JSON parsing beats strict `response_format=json_object` on reasoning models (CoT leaks break strict mode); never put `<placeholder>` pseudo-syntax in prompts demanding pure JSON — show a concrete filled example
- Layered grading localizes failures: retrieval miss = embedding/search problem; unsupported answer = generation problem
- SQLite `(x,)` tuple discipline: a 1-tuple needs a comma, `(x)` is just a grouped value — sqlite3 iterates a bare str into N bindings
- Two stores, no transaction: Qdrant + SQLite hold related data and are synced only by caller order (ingest both / delete both) — the canonical no-database double-write consistency smell, flagged for the journaling/DB phase
- Logs: `TimedRotatingFileHandler` (when=midnight, backupCount=7) chosen over `RotatingFileHandler` — "what happened Tuesday at 3am?" is a time question; one file/day beats size partitions
- Logs: console + file share one JSONFormatter — identical shape, Loki-ingestable later
- `hashlib` sha256 fingerprint of content in SQLite row — duplicates guard for re-ingest without byte-compare of full text
- Observability signal routing (20): traces → OTLP → Collector → Tempo; metrics → Prometheus pull (host-gateway); logs → file → promtail → Loki (json stage promotes trace_id/span_id/level to labels — log→trace bridge at ingestion)
- SLO alerting (21): error ratio computed once as a Prometheus recording rule, then evaluated in the Grafana alert — never repeat the same PromQL across alert rules; alert on budget burn, not raw metric levels
- Dashboard layout = ER triage (21): vitals (down? errors?) → diagnostics (where does the time go) → deep-dive (log/trace evidence); latency SLO drawn as a threshold line on the p95 panel
- Grafana provisioning = declarative infra (21): datasources/dashboards/alert rules are files with stable UIDs so cross-references survive renames; Prometheus datasource got `uid: prometheus` so alert rules can target it
- Hash-only API keys (23): full key is a 128-bit secret shown exactly once at `create()`; DB stores `sha256(key)` — a DB leak yields no usable keys, same dedup/fingerprint mind-set as `content_hash`
- `Annotated[..., Depends()]` not `x = Depends()` (23): the `= Depends()` FastAPI idiom trips Ruff B008 (function call in argument defaults); moving the dependency into the annotation is both lint-clean and the modern FastAPI style
- Auth-before-compute (23): dependency 401 fires before the handler runs, so unauthenticated expensive routes (`/embeddings`, `/rag`) never cold-start the ~30s embedding model
- HTTP status honesty (23): missing AND invalid keys both → 401 (`WWW-Authenticate: Bearer`), never 403 (that's authenticated-but-forbidden); `auto_error=False` because `HTTPBearer`'s default raises 403 on missing headers
- In-memory sliding window (23): per-key `deque` of `time.monotonic()` timestamps, single process only — each uvicorn worker has its own counter, so distributed rate limiting needs shared state (Redis)

## Teaching Rules
1. No dumping solutions — hints first, increase progressively
2. Ask guiding questions when stuck
3. Review code like Staff Engineer
4. Keep developer in struggle zone as long as possible
5. User types all code, tutor explains and reviews
6. Explain the "why" not just the "what"
7. Never edit files without asking — tell user what to edit

## Next Topics
20. **Observability Stack (Docker)** — DONE — config written, bootstrap run deferred to final assembly
21. **Monitoring Dashboards** — DONE — SLOs, triage dashboard, alert rules provisioned (config only)
22. **Streaming SSE** — DONE — opt-in SSE, configurable max_tokens, TTFT metric
23. **Auth & API Keys** — DONE — Bearer keys (hash-only), per-key rate limiting, CLI, auth metrics
24. Background jobs
25. Deployment
26. Production architecture
27. Capstone project

## New Machine Setup Notes (WSL Ubuntu 24)
- Python 3.14 IS stable (released Oct 2025); if tooling calls it pre-release, metadata is stale or an RC got cached — `uv python install 3.14`
- Keep repo in Linux FS (`~/...`), not `/mnt/c/...`, or file-watching/reload breaks
- LLM switch: Nemotron via NVIDIA API is OpenAI-compatible — only change `base_url` + model name in `app/services/llm.py` and the model string in agent.py/agent_graph.py ("qwen/qwen3.6-27b")
- `uv run fastapi dev` ≈ `uv run uvicorn app.main:app --reload` (needs `fastapi[standard]`; current pyproject has bare fastapi so uvicorn command works as-is)
- After clone on new machine: `uv sync`, copy `.env` with GROQ/NVIDIA key, then document ingestion before RAG tests
- VS Code MUST connect via Remote-WSL (green `WSL: Ubuntu-E` badge bottom-left); opening the folder over `\\wsl.localhost` in a local window breaks Pylance package resolution and kills the integrated terminal
- Kill a stale dev server family-wide: `pkill -9 -f uvicorn` (fastapi dev's watcher respawns killed workers); prefer `ss -tlnp | grep PORT` over lsof in WSL (lsof walks /mnt/c and can hang)
- opencode TUI ctrl+enter newline on Windows Terminal: sendInput action `\u001b[13;5u` + optional `~/.config/opencode/tui.json` keybinds file

## Important Context
- Ruff and pyright both pass on all files
- Server runs on localhost:8000
- Test MCP with: `PYTHONPATH=. uv run python tools/mcp_client.py documents`
- Test agents side-by-side with: `PYTHONPATH=. uv run python tools/test_agent_graph.py`
- Test SSE streaming with: `PYTHONPATH=. uv run python tools/stream_test.py`
- Manage API keys with: `PYTHONPATH=. uv run python tools/manage_keys.py create NAME` / `list` / `revoke KEY_ID`
- Run eval suite with: `PYTHONPATH=. uv run python tools/run_eval.py` (exit 1 = suite FAIL; currently PASS, avg 4.60/5)
- Document ingestion needed before RAG/agent tests work
- Inspect structured logs in the server stdout (JSON lines) and `logs/app.log` (timed rotation, one file/day, 7-day retention); `request_id` correlates a request's journey
- Prometheus metrics at `/metrics` for LLM latency/tokens (segments: tool_round/final/agent_round/agent_graph/agent_mcp) and HTTP count/duration (path label uses route pattern, `/metrics` excluded)
- The `suppress(BrokenPipeError)` in servers/documents.py may need attention — was replaced with `suppress(BaseExceptionGroup)` then removed when switching to `anyio.run()`
