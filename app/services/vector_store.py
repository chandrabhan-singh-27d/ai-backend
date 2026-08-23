from typing import TypedDict

from app.services.embeddings import cosine_similarity


class Document(TypedDict):
    text: str
    embedding: list[float]


class ScoredDocument(TypedDict):
    id: str
    text: str
    score: float


store: dict[str, Document] = {}


def add(doc_id: str, text: str, embedding: list[float]) -> None:
    store[doc_id] = {"text": text, "embedding": embedding}


def delete(doc_id: str) -> None:
    store.pop(doc_id, None)


def search(query_embedding: list[float], top_k: int = 3) -> list[ScoredDocument]:
    scored: list[ScoredDocument] = []
    for doc_id, doc in store.items():
        score = cosine_similarity(query_embedding, doc["embedding"])
        scored.append({"id": doc_id, "text": doc["text"], "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
