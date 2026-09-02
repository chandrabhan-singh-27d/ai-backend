# Continuation Prompt for AI Backend Project

## Project Overview
Building a production-grade AI backend incrementally with Python/FastAPI/Groq. Project at `/home/chandrabhan/project/ai-backend`. Teaching style: guided discovery, no dumping solutions, Staff Engineer code review, keep developer stuck as long as possible.

## User Profile
- Experienced JS/TS backend engineer (~5 years), no Python/AI background
- Types all code manually, tutor explains problems and reviews
- Shell: zsh with powerlevel10k, VSCode with Ruff + Pylance
- Python 3.14, pyright strict mode, Ruff rules `["E", "F", "I", "UP", "B", "SIM", "RUF"]`, line-length 100
- LLM: Groq (GROQ_API_KEY), no OpenAI/Anthropic keys

## What's Built (Topics 1-16 ✅)

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

### Key Files
- `app/main.py` — mounts 6 routers (health, models, demo, chat, embeddings, documents, rag)
- `app/services/llm.py` — AsyncOpenAI + Groq, TOOLS (ChatCompletionToolParam), TOOL_MAP, chat() with tools_enabled; qwen reasoning hidden via `reasoning_format` extra_body + `_strip_reasoning` fallback
- `app/services/embeddings.py` — SentenceTransformer, embed(), cosine_similarity()
- `app/services/vector_store.py` — store dict, Document/ScoredDocument TypedDicts, add/search/delete
- `app/services/tools.py` — calculate() with eval whitelist
- `app/services/rag.py` — build_prompt(), answer_question()
- `app/services/agent.py` — run_agent() with tool loop
- `app/services/agent_graph.py` — LangGraph agent (AgentState, call_llm, run_tools, route_after_llm, graph, run_agent_graph)
- `app/services/agent_mcp.py` — run_mcp_agent() connecting to MCP server
- `app/services/context.py` — RequestContext dataclass, ContextVar, token-based set/reset
- `app/services/logging.py` — JSONFormatter (request-scoped fields) + setup_logging
- `app/services/metrics.py` — Prometheus metrics (LLM latency/tokens, HTTP count/duration) + measure_llm_call
- `app/middlewares/request_context.py` — request_id/client_id middleware + HTTP metrics
- `app/routers/metrics.py` — GET /metrics scrape endpoint
- `servers/documents.py` — MCP 2.0 server (list_tools, call_tool callbacks)
- `tools/mcp_client.py` — MCPTestClient with DocumentsTest class
- `tools/test_agent_graph.py` — side-by-side hand-rolled vs langgraph agent test
- `tools/eval_cases.json` — golden eval cases (questions, expected_doc_ids, expected_facts, answerable flag)
- `tools/corpus.json` — seed documents so the eval suite is self-contained
- `tools/run_eval.py` — eval harness (seed → retrieval check → generate → judge → report → exit code)
- `app/routers/chat.py` — /chat, /chat/tools, /agent, /agent/mcp, /agent/graph

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

## Teaching Rules
1. No dumping solutions — hints first, increase progressively
2. Ask guiding questions when stuck
3. Review code like Staff Engineer
4. Keep developer in struggle zone as long as possible
5. User types all code, tutor explains and reviews
6. Explain the "why" not just the "what"
7. Never edit files without asking — tell user what to edit

## Next Topics
17. **Auth & API Keys** — NEXT
18. Background jobs
19. Deployment
20. Production architecture
21. Capstone project

**Planned interlude before/with 19:** swap in-memory vector store for Qdrant-in-Docker behind the existing `add`/`search`/`delete` interface, using the eval suite as the regression safety net (user decision).

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
- Run eval suite with: `PYTHONPATH=. uv run python tools/run_eval.py` (exit 1 = suite FAIL; currently PASS, avg 4.60/5)
- Document ingestion needed before RAG/agent tests work
- Inspect structured logs in the server stdout (JSON lines); `request_id` correlates a request's journey
- Prometheus metrics at `/metrics` for LLM latency/tokens (segments: tool_round/final/agent_round/agent_graph/agent_mcp) and HTTP count/duration (path label uses route pattern, `/metrics` excluded)
- The `suppress(BrokenPipeError)` in servers/documents.py may need attention — was replaced with `suppress(BaseExceptionGroup)` then removed when switching to `anyio.run()`
