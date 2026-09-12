import hashlib

from fastapi import APIRouter
from pydantic import BaseModel

from app.dependencies import PROTECTED
from app.services.embeddings import embed
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
    top_k: int = 3


class SearchResult(BaseModel):
    id: str
    text: str
    score: float


@router.post("/documents")
def ingest_document(request: IngestRequest) -> dict[str, str]:
    embedding = embed([request.text])
    get_store().add(doc_id=request.id, text=request.text, embedding=embedding[0])
    content_hash = hashlib.sha256(request.text.encode()).hexdigest()
    get_metadata_store().add_document(
        doc_id=request.id,
        title=request.title or request.id,
        content_hash=content_hash,
        source=request.source,
        chunk_count=1,
    )
    return {"status": "ok", "id": request.id}


@router.post("/search")
def search_documents(request: SearchRequest) -> list[SearchResult]:
    query_embedding = embed([request.query])[0]
    results = get_store().search(query_embedding, top_k=request.top_k)
    return [SearchResult(**r) for r in results]


@router.get("/documents/metadata")
def list_metadata() -> list[dict[str, object]]:
    return get_metadata_store().list_documents()


@router.delete("/documents/{doc_id}")
def delete_document(doc_id: str) -> dict[str, str]:
    get_store().delete(doc_id)
    get_metadata_store().delete_document(doc_id=doc_id)
    return {"status": "deleted", "id": doc_id}
