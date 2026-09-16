import asyncio
import hashlib
import logging
from collections.abc import Awaitable, Callable

from app.services.embeddings import embed
from app.services.job_store import get_job_store
from app.services.metadata_store import get_metadata_store
from app.services.vector_store import get_store

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, object]], Awaitable[dict[str, object]]]


async def _ingest_document(payload: dict[str, object]) -> dict[str, object]:
    doc_id = str(payload["id"])
    text = str(payload["text"])
    title = str(payload.get("title", ""))
    source = str(payload.get("source", "unknown"))
    embedding = await embed([text])
    get_store().add(doc_id=doc_id, text=text, embedding=embedding[0])
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    get_metadata_store().add_document(
        doc_id=doc_id, title=title, content_hash=content_hash, source=source, chunk_count=1
    )

    return {"status": "ok", "id": doc_id}


JOB_HANDLERS: dict[str, JobHandler] = {"ingest_document": _ingest_document}


async def run_worker_loop(poll_interval: float = 0.5) -> None:
    store = get_job_store()

    while True:
        job = store.claim()
        if job is None:
            await asyncio.sleep(poll_interval)
            continue

        try:
            handler = JOB_HANDLERS[job["kind"]]
            result = await handler(job["payload"])
            store.complete(job["id"], result=result)
        except Exception as e:
            logger.exception("job %s failed", job["id"])
            store.fail(job["id"], str(e))
