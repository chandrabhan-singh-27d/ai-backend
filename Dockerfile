FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /bin/
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev
COPY app ./app

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