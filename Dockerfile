# syntax=docker/dockerfile:1

# ---------------------------------------------------------------------------
# Stage 1 — install dependencies (reused across app-code changes)
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/
WORKDIR /app

ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy

# Cache uv's download + build caches on the HOST so they survive across builds.
# Without these, every lockfile change forces uv to re-download all 474 packages
# and re-compile every source distribution from scratch.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY app ./app

# ---------------------------------------------------------------------------
# Stage 2 — runtime (minimal image, no uv binary, no build caches)
# ---------------------------------------------------------------------------
FROM python:3.14-slim AS runtime
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/app /app/app
WORKDIR /app

ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

RUN useradd --create-home appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
