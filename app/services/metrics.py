from contextlib import contextmanager
from time import perf_counter

from prometheus_client import Counter, Histogram

LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "Latency of LLM chat completion calls",
    labelnames=["model", "tools_enabled", "segment"],
)

LLM_TOKENS = Counter(
    "llm_tokens_total", "Total tokens processed by LLM Calls", labelnames=["model", "tools_enabled"]
)

HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests completed", labelnames=["method", "path", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds", labelnames=["method", "path"]
)

@contextmanager
def measure_llm_call(model: str, tools_enabled: bool, segment: str):
    start = perf_counter()

    try:
        yield
    finally:
        LLM_LATENCY.labels(model=model, tools_enabled=str(tools_enabled), segment=segment).observe(
            perf_counter() - start
        )
