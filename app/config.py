import os

# --- LLM ---
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "400"))
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "600"))
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
LLM_REASONING_FORMAT = os.getenv("LLM_REASONING_FORMAT", "hidden")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "none")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# --- Agent ---
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "5"))
AGENT_GRAPH_RECURSION_LIMIT = int(os.getenv("AGENT_GRAPH_RECURSION_LIMIT", "10"))

# --- Jobs / worker ---
JOB_MAX_ATTEMPTS = int(os.getenv("JOB_MAX_ATTEMPTS", "3"))
JOB_HEARTBEAT_TIMEOUT_SECONDS = int(os.getenv("JOB_HEARTBEAT_TIMEOUT_SECONDS", "300"))

# --- RAG ---
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# --- Embeddings (Hugging Face Inference API, no local torch) ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
HF_TOKEN = os.getenv("HF_TOKEN", "")
EMBEDDING_TIMEOUT_SECONDS = float(os.getenv("EMBEDDING_TIMEOUT_SECONDS", "60"))
HF_EMBEDDINGS_URL = os.getenv(
    "HF_EMBEDDINGS_URL",
    f"https://router.huggingface.co/hf-inference/models/{EMBEDDING_MODEL}/pipeline/feature-extraction",
)

# --- Vector store (Qdrant) ---
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "documents")

# --- SQLite databases ---
JOBS_DB_PATH = os.getenv("JOBS_DB_PATH", "data/jobs.db")
KEYS_DB_PATH = os.getenv("KEYS_DB_PATH", "data/keys.db")
METADATA_DB_PATH = os.getenv("METADATA_DB_PATH", "data/app.db")
MODELS_DB_PATH = os.getenv("MODELS_DB_PATH", "data/models.db")

# --- Auth / rate limiting ---
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
# "memory" is per-process (valid for a single uvicorn worker); "redis" shares state
# across workers via REDIS_URL (fixed-window counters).
RATE_LIMIT_STRATEGY = os.getenv("RATE_LIMIT_STRATEGY", "memory")
REDIS_URL = os.getenv("REDIS_URL", "")

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Observability ---
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
OTEL_TRACING_ENABLED = os.getenv("OTEL_TRACING_ENABLED", "true").lower() in {
    "1",
    "true",
    "yes",
}

# --- Demo endpoints (/slow-sync, /slow-async, /slow-blocked) ---
DEMO_ENDPOINTS = os.getenv("DEMO_ENDPOINTS", "false").lower() in {"1", "true", "yes"}

# --- Eval (tools/run_eval.py) ---
EVAL_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")
# gpt-oss accepts only low/medium/high (unlike qwen's none)
EVAL_JUDGE_REASONING_EFFORT = os.getenv("EVAL_JUDGE_REASONING_EFFORT", "low")
