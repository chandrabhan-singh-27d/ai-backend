# AI Backend - Project Progress

> **Next session?** See [CONTINUATION.md](CONTINUATION.md) for full context to hand off to the next agent.

## Teaching & Development Style

### Rules
1. **No dumping solutions** — Give hints first, increase progressively based on struggle level
2. **Guided discovery** — When stuck on a bug, ask guiding questions instead of fixing immediately
3. **Staff-level review** — Review code like a Staff Engineer, not a tutorial
4. **Keep stuck** — Maximize learning by keeping the developer in the struggle zone as long as possible
5. **User types all code** — Tutor explains problems, suggests approaches, reviews results
6. **Explain the "why"** — Not just what to do, but why it works that way
7. **Incremental complexity** — Each topic builds on the previous one

### Project Conventions
- **Linting**: Ruff with rules `["E", "F", "I", "UP", "B", "SIM", "RUF"]`, line-length 100
- **Type checking**: Pyright strict mode from day one
- **Python version**: 3.14
- **Package manager**: uv
- **Shell**: zsh with powerlevel10k
- **Editor**: VSCode with Ruff extension, Pylance
- **LLM Provider**: Groq (OpenAI-compatible API)

---

## Progress Tracker

### Phase 1: Foundations

| # | Topic | Status | Key Concepts |
|---|---|---|---|
| 1 | Python project structure | ✅ | Flat layout, `app/` package, `__init__.py` |
| 2 | venv & dependency management | ✅ | `uv venv`, `uv add`, `pyproject.toml`, `uv.lock` |
| 3 | FastAPI basics | ✅ | App object, routers, composition root, `include_router` |
| 4 | Pydantic | ✅ | `BaseModel` for requests, `TypedDict` for internal shapes, 422 responses |
| 5 | Async programming | ✅ | `async def` vs `def`, event loop, blocking, threadpool |
| 6 | HTTP clients | ✅ | `httpx.AsyncClient`, async context managers, error handling |
| 7 | LLM SDKs | ✅ | OpenAI SDK with Groq `base_url`, service layer pattern |
| 8 | Embeddings | ✅ | `sentence-transformers`, cosine similarity, `all-MiniLM-L6-v2` |

### Phase 2: Core AI Patterns

| # | Topic | Status | Key Concepts |
|---|---|---|---|
| 9 | Vector databases | ✅ | In-memory store, cosine search, `TypedDict` for documents |
| 10 | RAG | ✅ | Retrieve → Augment → Generate, context injection |
| 11 | Tool calling | ✅ | OpenAI function calling, `ChatCompletionToolParam`, tool routing |
| 12 | MCP | ✅ | Model Context Protocol, stdio transport, `on_list_tools`/`on_call_tool` callbacks |
| 13 | AI Agents | ✅ | LLM loop, autonomous tool usage, MCP client integration |

### Phase 3: Production Readiness

| # | Topic | Status | Key Concepts |
|---|---|---|---|
| 14 | Agent Frameworks | ✅ | LangGraph, StateGraph, nodes/edges, reducers, recursion_limit |
| 15 | Evaluation | ✅ | LLM-as-judge, rubric scoring (1–5), golden fixtures, retrieval vs faithfulness layers |
| 16 | Observability | ✅ | Structured JSON logging, request tracing via ContextVar, Prometheus metrics |
| 17 | Auth & API Keys | ⬜ | Authentication, rate limiting, API key management |
| 18 | Background jobs | ⬜ | Task queues, async processing |
| 19 | Deployment | ⬜ | Docker, CI/CD, hosting |
| 20 | Production architecture | ⬜ | Scalability, reliability, cost optimization |
| 21 | Capstone project | ⬜ | Full-stack AI application |

---

## Architecture Overview

```
ai-backend/
├── app/
│   ├── main.py                    # Composition root
│   ├── routers/
│   │   ├── health.py              # GET /health
│   │   ├── models.py              # GET/POST /models (TypedDict + Pydantic)
│   │   ├── demo.py                # Sync/async demos, httpx
│   │   ├── chat.py                # POST /chat, /chat/tools, /agent, /agent/mcp, /agent/graph
│   │   ├── embeddings.py          # POST /embeddings, /similarity
│   │   ├── documents.py           # POST /documents, /search, DELETE /documents/{id}
│   │   └── metrics.py             # GET /metrics (Prometheus scrape endpoint)
│   ├── middlewares/
│   │   └── request_context.py     # Mints request_id, sets ContextVar, HTTP + LLM metrics
│   └── services/
│       ├── llm.py                 # OpenAI client (Groq), tools, TOOLS, TOOL_MAP
│       ├── embeddings.py          # sentence-transformers, cosine similarity
│       ├── vector_store.py        # In-memory vector store (TypedDict)
│       ├── tools.py               # Calculator tool (eval with whitelist)
│       ├── rag.py                 # RAG pipeline (retrieve → augment → generate)
│       ├── agent.py               # Direct tool-calling agent
│       ├── agent_graph.py         # LangGraph agent (AgentState, nodes, conditional edges)
│       ├── agent_mcp.py           # MCP-based agent (dynamic tool discovery)
│       ├── context.py             # RequestContext dataclass + ContextVar (token-reset safe)
│       ├── logging.py             # JSONFormatter + setup_logging (structured, request-scoped)
│       └── metrics.py             # Prometheus histograms/counters (LLM + HTTP) + measure helper
├── servers/
│   └── documents.py               # MCP server (documents CRUD)
├── tools/
│   ├── mcp_client.py              # MCP test client
│   ├── test_agent_graph.py        # Side-by-side hand-rolled vs LangGraph agent test
│   ├── eval_cases.json            # Golden RAG eval cases (incl. unanswerable refusal case)
│   ├── corpus.json                # Seed corpus for self-contained eval runs
│   └── run_eval.py                # Eval harness (seed → retrieve-check → generate → judge → report)
├── pyproject.toml                 # Project config, deps, ruff, pyright
├── .env                           # GROQ_API_KEY (gitignored)
├── .gitignore
└── uv.lock
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Flat package layout | Simple, no nested `src/` needed for this project |
| Pydantic for API, TypedDict for internal | Pydantic validates input, TypedDict types internal data without overhead |
| Service layer pattern | Business logic in `services/`, routing in `routers/` |
| In-memory vector store first | Teaches the abstraction before adding external dependencies |
| MCP over hardcoded tools | Decoupled architecture, tools discoverable at runtime |
| Two agent implementations | Shows tradeoffs: direct (simple) vs MCP (flexible) |
| `uv` over `pip` | Faster, better dependency resolution, lockfile support |
| Judge = separate client, temperature=0 | Eval concerns stay out of prod service; frozen judge = non-flaky suite |
| Extraction over strict JSON mode | Reasoning models leak CoT into structured output; parse defensively instead of coercing format |
| Layered grading (retrieval check vs LLM judge) | Score failures localize: wrong docs = embedding problem, unsupported claims = generation problem |
| ContextVar + Token.reset for request state | Async-safe per-task state; reset prevents stale `request_id` leaking into background tasks/threads |
| JSON formatter reading the same ContextVar | Every log line auto-carries `request_id`/`client_id` regardless of logger or call depth |
| Prometheus `client` (not auto-instrument wizard) | Learn the exposition format + cardinality discipline; metrics only where they matter (LLM, HTTP) |
| Route pattern (`scope["route"].path`) not concrete URL for `path` label | Avoids cardinality explosion from path parameters like `/documents/{id}` |

---

## Files Changed Log

### Topic 8: Embeddings
- Created `app/services/embeddings.py`
- Created `app/routers/embeddings.py`
- Added `sentence-transformers` dependency
- Added pyright ignore comments for untyped ML library

### Topic 9: Vector Store
- Created `app/services/vector_store.py`
- Created `app/routers/documents.py`
- Used `TypedDict` for `Document` and `ScoredDocument`

### Topic 10: RAG
- Created `app/services/rag.py`
- Created `app/routers/rag.py`

### Topic 11: Tool Calling
- Created `app/services/tools.py`
- Updated `app/services/llm.py` (TOOLS, TOOL_MAP, chat with tools_enabled)
- Updated `app/routers/chat.py` (/chat/tools endpoint)

### Topic 12: MCP
- Created `servers/documents.py` (MCP server)
- Created `tools/mcp_client.py` (MCP test client)
- Added `mcp` dependency

### Topic 13: Agents
- Created `app/services/agent.py` (direct tool-calling agent)
- Created `app/services/agent_mcp.py` (MCP-based agent)
- Updated `app/routers/chat.py` (/agent, /agent/mcp endpoints)
- Added document tools to TOOLS/TOOL_MAP in llm.py

### Topic 14: Agent Frameworks
- Created `app/services/agent_graph.py` (AgentState reducer, call_llm/run_tools nodes, route_after_llm conditional edge)
- Created `tools/test_agent_graph.py` (side-by-side hand-rolled vs LangGraph comparison)
- Updated `app/routers/chat.py` (/agent/graph endpoint)
- Added `langgraph` dependency

### Topic 15: Evaluation
- Created `tools/eval_cases.json` (5 golden cases incl. unanswerable refusal case)
- Created `tools/corpus.json` (seed corpus for self-contained runs)
- Created `tools/run_eval.py` (idempotent seeding, independent retrieval check, temperature-0 judge, defensive verdict parsing, PASS/FAIL exit code)
- Fixed `app/services/llm.py`: qwen chain-of-thought leaked into user-facing answers; added `reasoning_format: hidden` + `_strip_reasoning` safety net

### Topic 12–16 addendum (tracing, logging, metrics)
- Created `app/services/context.py` (RequestContext dataclass, ContextVar, token-based set/reset)
- Created `app/services/logging.py` (JSONFormatter, setup_logging)
- Created `app/services/metrics.py` (LLM_LATENCY/LLM_TOKENS/HTTP_REQUESTS/HTTP_REQUEST_DURATION, measure_llm_call)
- Created `app/middlewares/request_context.py` (request_id/client_id ContextVar middleware + HTTP metrics)
- Created `app/routers/metrics.py` (Prometheus scrape endpoint)
- Updated `app/main.py` (setup_logging, register middleware + metrics router)
- Added application logging to `llm.py` (llm_call), `rag.py` (rag_retrieval), `chat.py` (error paths), `request_context.py` (request lifecycle)
- Instrumented agent LLM calls (`agent.py`/`agent_graph.py`/`agent_mcp.py`) with `measure_llm_call` + token counters
- Added `prometheus-client` dependency
