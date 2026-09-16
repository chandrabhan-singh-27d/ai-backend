import os

# --- LLM ---
LLM_MODEL = os.getenv("LLM_MODEL", "qwen/qwen3.8-27b")
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "400"))
LLM_REASONING_FORMAT = os.getenv("LLM_REASONING_FORMAT", "hidden")
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "none")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")

# --- Agent ---
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "5"))
AGENT_GRAPH_RECURSION_LIMIT = int(os.getenv("AGENT_GRAPH_RECURSION_LIMIT", "10"))

# --- RAG ---
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "3"))

# --- Embeddings (Hugging Face Inference API, no local torch) ---
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "384"))
HF_TOKEN = os.getenv("HF_TOKEN", "")
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

# --- Auth / rate limiting ---
RATE_LIMIT_MAX_REQUESTS = int(os.getenv("RATE_LIMIT_MAX_REQUESTS", "60"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))

# --- Logging ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# --- Eval (tools/run_eval.py) ---
EVAL_JUDGE_MODEL = os.getenv("EVAL_JUDGE_MODEL", "openai/gpt-oss-120b")
