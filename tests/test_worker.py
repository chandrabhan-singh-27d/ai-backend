import asyncio
import hashlib

import app.services.worker as worker


class FakeVectorStore:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def add(self, doc_id: str, text: str, embedding: list[float]) -> None:
        self.items[doc_id] = text


class FakeMetadataStore:
    def __init__(self) -> None:
        self.docs: dict[str, dict[str, object]] = {}
        self.hashes: dict[str, dict[str, object]] = {}

    def add_document(
        self,
        doc_id: str,
        title: str,
        content_hash: str,
        source: str = "unknown",
        chunk_count: int = 1,
    ) -> None:
        row = {"doc_id": doc_id, "content_hash": content_hash}
        self.docs[doc_id] = row
        self.hashes[content_hash] = row

    def find_by_content_hash(self, content_hash: str) -> dict[str, object] | None:
        return self.hashes.get(content_hash)


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_duplicate_content_skips_embedding_and_vector(monkeypatch) -> None:
    vectors = FakeVectorStore()
    metadata = FakeMetadataStore()
    metadata.add_document("doc-a", "a", _hash("same text"), source="x", chunk_count=1)

    calls: list[list[str]] = []

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(worker, "get_store", lambda: vectors)
    monkeypatch.setattr(worker, "get_metadata_store", lambda: metadata)
    monkeypatch.setattr(worker, "embed", fake_embed)

    result = asyncio.run(worker._ingest_document({"id": "doc-b", "text": "same text"}))

    assert result["status"] == "duplicate"
    assert result["deduped_against"] == "doc-a"
    assert calls == []
    assert "doc-b" not in vectors.items
    assert "doc-b" in metadata.docs


def test_new_content_embeds_and_vectors(monkeypatch) -> None:
    vectors = FakeVectorStore()
    metadata = FakeMetadataStore()
    calls: list[list[str]] = []

    async def fake_embed(texts: list[str]) -> list[list[float]]:
        calls.append(texts)
        return [[1.0, 0.0]]

    monkeypatch.setattr(worker, "get_store", lambda: vectors)
    monkeypatch.setattr(worker, "get_metadata_store", lambda: metadata)
    monkeypatch.setattr(worker, "embed", fake_embed)

    result = asyncio.run(worker._ingest_document({"id": "doc-a", "text": "fresh text"}))

    assert result["status"] == "ok"
    assert calls == [["fresh text"]]
    assert vectors.items["doc-a"] == "fresh text"
    assert metadata.docs["doc-a"]["content_hash"] == _hash("fresh text")