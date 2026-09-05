import uuid
from typing import TypedDict

from qdrant_client import QdrantClient, models

Distance = models.Distance


def _point_id(doc_id: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, doc_id))


class Document(TypedDict):
    text: str
    embedding: list[float]


class ScoredDocument(TypedDict):
    id: str
    text: str
    score: float


class VectorStore:
    def __init__(self, client: QdrantClient, collection: str, vector_size: int) -> None:
        self.client = client
        self.collection = collection

        if not self.client.collection_exists(collection):
            self.client.create_collection(
                collection_name=collection,
                vectors_config=models.VectorParams(size=vector_size, distance=Distance.COSINE),
            )

    def add(self, doc_id: str, text: str, embedding: list[float]) -> None:
        self.client.upsert(
            collection_name=self.collection,
            points=[
                models.PointStruct(
                    id=_point_id(doc_id), vector=embedding, payload={"doc_id": doc_id, "text": text}
                )
            ],
        )

    def search(self, query_embedding: list[float], top_k: int = 3) -> list[ScoredDocument]:
        response = self.client.query_points(
            collection_name=self.collection, query=query_embedding, limit=top_k, with_payload=True
        )

        results: list[ScoredDocument] = []

        for point in response.points:
            payload = point.payload or {}
            doc_id = payload.get("doc_id", "")
            text = payload.get("text", "")
            assert isinstance(doc_id, str)
            assert isinstance(text, str)
            results.append({"id": doc_id, "text": text, "score": point.score})
        return results

    def delete(self, doc_id: str) -> None:
        self.client.delete(collection_name=self.collection, points_selector=[_point_id(doc_id)])

    def get(self, doc_id: str) -> str | None:
        records = self.client.retrieve(
            collection_name=self.collection, ids=[_point_id(doc_id)], with_payload=True
        )

        if not records:
            return None
        payload = records[0].payload or {}
        text = payload.get("text")
        assert isinstance(text, str)
        return text

    def exists(self, doc_id: str) -> bool:
        return bool(
            self.client.retrieve(
                collection_name=self.collection,
                ids=[_point_id(doc_id)],
            )
        )

    def count(self) -> int:
        return self.client.count(collection_name=self.collection, exact=True).count

    def list_all(self) -> list[dict[str, str]]:
        records = self.client.scroll(
            collection_name=self.collection,
            limit=1000,
            with_payload=True,
        )[0]

        docs: list[dict[str, str]] = []
        for record in records:
            payload = record.payload or {}
            doc_id = payload.get("doc_id", "")
            text = payload.get("text", "")
            assert isinstance(doc_id, str)
            assert isinstance(text, str)
            docs.append({"id": doc_id, "text": text})
        return docs


_store: VectorStore | None = None


def get_store() -> VectorStore:
    global _store
    if _store is None:
        _store = VectorStore(
            client=QdrantClient(url="http://localhost:6333"),
            collection="documents",
            vector_size=384,
        )

    return _store
