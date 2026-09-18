# syntax=docker/dockerfile:1

# Single-stage build: avoids materializing the multi-GB venv twice
# (builder venv layer + runtime COPY layer = ~11GB of cache for one build).
FROM python:3.14.7-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/
WORKDIR /app

ENV UV_LINK_MODE=copy

# uv's download/build caches live on the host via the cache mount, so
# rebuilds reuse deps (npm-ci style) instead of re-downloading all 474
# transitive packages (PyTorch/sentence-transformers stack).
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev \
    && rm -f /uv /uvx

COPY app ./app
COPY servers ./servers

ENV PATH=/app/.venv/bin:$PATH
ENV PYTHONPYCACHEPREFIX=/tmp/pycache

RUN useradd --create-home appuser \
    && mkdir -p /app/data /app/logs \
    && chown -R appuser /app

USER appuser
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]