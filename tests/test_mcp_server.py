import asyncio
import hashlib

from mcp import types

import servers.documents as mcp_server


class FakeVectorStore:
    def __init__(self) -> None:
        self.items: dict[str, str] = {}

    def add(self, doc_id: str, text: str, embedding: list[float]) -> None:
        self.items[doc_id] = text

    def exists(self, doc_id: str) -> bool:
        return doc_id in self.items

    def delete(self, doc_id: str) -> None:
        self.items.pop(doc_id, None)


class FakeMetadataStore:
    def __init__(self) -> None:
        self.rows: dict[str, dict[str, object]] = {}

    def add_document(
        self,
        doc_id: str,
        title: str,
        content_hash: str,
        source: str = "unknown",
        chunk_count: int = 1,
    ) -> None:
        self.rows[doc_id] = {
            "doc_id": doc_id,
            "title": title,
            "content_hash": content_hash,
            "source": source,
        }

    def delete_document(self, doc_id: str) -> None:
        self.rows.pop(doc_id, None)


def _params(name: str, arguments: dict[str, object]) -> types.CallToolRequestParams:
    return types.CallToolRequestParams(name=name, arguments=arguments)


async def _fake_embed(texts: list[str]) -> list[list[float]]:
    return [[1.0, 0.0]]


def _patch_stores(monkeypatch) -> tuple[FakeVectorStore, FakeMetadataStore]:
    vectors = FakeVectorStore()
    metadata = FakeMetadataStore()
    monkeypatch.setattr(mcp_server, "get_store", lambda: vectors)
    monkeypatch.setattr("app.services.embeddings.embed", _fake_embed)
    monkeypatch.setattr("app.services.metadata_store.get_metadata_store", lambda: metadata)
    return vectors, metadata


def test_mcp_add_document_syncs_metadata(monkeypatch) -> None:
    vectors, metadata = _patch_stores(monkeypatch)

    result = asyncio.run(
        mcp_server.handle_call_tool(
            None, _params("add_document", {"doc_id": "mcp-1", "text": "hello"})
        )
    )

    assert result.is_error is False
    assert vectors.items["mcp-1"] == "hello"
    row = metadata.rows["mcp-1"]
    assert row["content_hash"] == hashlib.sha256(b"hello").hexdigest()
    assert row["source"] == "mcp"
    assert row["title"] == "mcp-1"


def test_mcp_delete_document_syncs_metadata(monkeypatch) -> None:
    vectors, metadata = _patch_stores(monkeypatch)
    vectors.items["mcp-1"] = "hello"
    metadata.rows["mcp-1"] = {
        "doc_id": "mcp-1",
        "title": "mcp-1",
        "content_hash": "h",
        "source": "mcp",
    }

    result = asyncio.run(
        mcp_server.handle_call_tool(None, _params("delete_document", {"doc_id": "mcp-1"}))
    )

    assert result.is_error is False
    assert "deleted" in result.content[0].text
    assert "mcp-1" not in vectors.items
    assert "mcp-1" not in metadata.rows


def test_mcp_delete_missing_document_reports_error(monkeypatch) -> None:
    _vectors, metadata = _patch_stores(monkeypatch)

    result = asyncio.run(
        mcp_server.handle_call_tool(None, _params("delete_document", {"doc_id": "nope"}))
    )

    assert result.is_error is True
    assert "not found" in result.content[0].text
    assert metadata.rows == {}