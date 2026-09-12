from contextlib import contextmanager
from time import perf_counter

from prometheus_client import Counter, Histogram

from app.services.tracing import get_tracer

LLM_LATENCY = Histogram(
    "llm_latency_seconds",
    "Latency of LLM chat completion calls",
    labelnames=["model", "tools_enabled", "segment"],
)

LLM_TTFT = Histogram(
    "llm_time_to_first_token_seconds",
    "Time from LLM API call start to first content token",
    labelnames=["model", "segment"],
)

LLM_TOKENS = Counter(
    "llm_tokens_total", "Total tokens processed by LLM Calls", labelnames=["model", "tools_enabled"]
)

HTTP_REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests completed", labelnames=["method", "path", "status"]
)

HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    labelnames=["method", "path"],
)

AUTH_FAILURES = Counter(
    "auth_failures_total", "Failed authentication and rate-limit attempts", labelnames=["reason"]
)


@contextmanager
def measure_llm_call(model: str, tools_enabled: bool, segment: str):
    start = perf_counter()

    with get_tracer().start_as_current_span(f"llm_call.{segment}"):
        try:
            yield
        finally:
            tools_label = "true" if tools_enabled else "false"
            LLM_LATENCY.labels(model=model, tools_enabled=tools_label, segment=segment).observe(
                perf_counter() - start
            )
