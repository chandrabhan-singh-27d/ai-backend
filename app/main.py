# pyright: reportMissingTypeStubs=false

from dotenv import load_dotenv

load_dotenv()

import asyncio  # noqa: E402
from collections.abc import AsyncGenerator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor  # noqa: E402

from app.middlewares.request_context import request_context_middleware  # noqa: E402
from app.routers import (  # noqa: E402
    chat,
    demo,
    documents,
    embeddings,
    health,
    jobs,
    metrics,
    models,
    rag,
)
from app.services.logging import setup_logging  # noqa: E402
from app.services.tracing import setup_tracing  # noqa: E402
from app.services.worker import run_worker_loop  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    worker = asyncio.create_task(run_worker_loop())
    try:
        yield
    finally:
        worker.cancel()
        await asyncio.gather(worker, return_exceptions=True)


setup_logging()
app = FastAPI(title="AI Backend", lifespan=lifespan)
setup_tracing()
FastAPIInstrumentor.instrument_app(app)
app.middleware("http")(request_context_middleware)
app.include_router(health.router)
app.include_router(models.router)
app.include_router(demo.router)
app.include_router(chat.router)
app.include_router(embeddings.router)
app.include_router(documents.router)
app.include_router(rag.router)
app.include_router(metrics.router)
app.include_router(jobs.router)
