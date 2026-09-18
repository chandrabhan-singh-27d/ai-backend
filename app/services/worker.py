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
    content_hash = hashlib.sha256(text.encode()).hexdigest()

    existing = await asyncio.to_thread(get_metadata_store().find_by_content_hash, content_hash)
    if existing is not None and str(existing["doc_id"]) != doc_id:
        await asyncio.to_thread(
            get_metadata_store().add_document,
            doc_id=doc_id,
            title=title,
            content_hash=content_hash,
            source=source,
            chunk_count=1,
        )
        return {"status": "duplicate", "id": doc_id, "deduped_against": existing["doc_id"]}

    embedding = await embed([text])
    await asyncio.to_thread(get_store().add, doc_id=doc_id, text=text, embedding=embedding[0])
    await asyncio.to_thread(
        get_metadata_store().add_document,
        doc_id=doc_id,
        title=title,
        content_hash=content_hash,
        source=source,
        chunk_count=1,
    )

    return {"status": "ok", "id": doc_id}


JOB_HANDLERS: dict[str, JobHandler] = {"ingest_document": _ingest_document}


async def run_worker_loop(poll_interval: float = 0.5) -> None:
    from app.config import JOB_MAX_ATTEMPTS

    store = get_job_store()

    while True:
        job = await asyncio.to_thread(store.claim)
        if job is None:
            await asyncio.sleep(poll_interval)
            continue

        try:
            handler = JOB_HANDLERS[job["kind"]]
            result = await handler(job["payload"])
            await asyncio.to_thread(store.complete, job["id"], result=result)
        except Exception as e:
            logger.exception("job %s failed (attempt %d)", job["id"], job["attempts"] + 1)
            if job["attempts"] + 1 >= JOB_MAX_ATTEMPTS:
                await asyncio.to_thread(store.fail, job["id"], str(e))
            else:
                await asyncio.to_thread(store.requeue, job["id"], str(e))
