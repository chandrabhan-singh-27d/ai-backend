import asyncio

from fastapi import APIRouter, Query, status
from pydantic import BaseModel, Field

from app.dependencies import PROTECTED
from app.services.embeddings import embed
from app.services.job_store import get_job_store
from app.services.metadata_store import get_metadata_store
from app.services.vector_store import get_store

router = APIRouter(dependencies=PROTECTED)


class IngestRequest(BaseModel):
    id: str
    text: str
    title: str = ""
    source: str = "unknown"


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=20)


class SearchResult(BaseModel):
    id: str
    text: str
    score: float


@router.post("/documents", status_code=status.HTTP_202_ACCEPTED)
def ingest_document(request: IngestRequest) -> dict[str, str]:
    job_id = get_job_store().create(
        "ingest_document",
        {
            "id": request.id,
            "text": request.text,
            "title": request.title,
            "source": request.source,
        },
    )
    return {"status": "accepted", "job_id": job_id}


@router.post("/search")
async def search_documents(request: SearchRequest) -> list[SearchResult]:
    query_embedding = (await embed([request.query]))[0]
    results = await asyncio.to_thread(get_store().search, query_embedding, request.top_k)
    return [SearchResult(**r) for r in results]


@router.get("/documents/metadata")
def list_metadata(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    return get_metadata_store().list_documents(limit=limit, offset=offset)


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    get_store().delete(doc_id)
    get_metadata_store().delete_document(doc_id=doc_id)
    return {"status": "deleted", "id": doc_id}
