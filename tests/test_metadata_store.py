import pytest

from app.services.metadata_store import MetadataStore


@pytest.fixture
def metadata_store(tmp_path) -> MetadataStore:
    return MetadataStore(db_path=str(tmp_path / "app.db"))


def test_add_get_delete(metadata_store: MetadataStore) -> None:
    metadata_store.add_document("doc-1", "Title", "hash-1", source="smoke", chunk_count=1)

    doc = metadata_store.get_document("doc-1")
    assert doc is not None
    assert doc["title"] == "Title"
    assert doc["content_hash"] == "hash-1"
    assert metadata_store.document_exists("doc-1") is True
    assert metadata_store.count() == 1

    metadata_store.delete_document("doc-1")
    assert metadata_store.get_document("doc-1") is None
    assert metadata_store.count() == 0


def test_find_by_content_hash(metadata_store: MetadataStore) -> None:
    metadata_store.add_document("doc-a", "A", "hash-1", source="s", chunk_count=2)
    metadata_store.add_document("doc-b", "B", "hash-2", source="s", chunk_count=1)

    found = metadata_store.find_by_content_hash("hash-2")
    assert found is not None
    assert found["doc_id"] == "doc-b"
    assert metadata_store.find_by_content_hash("hash-nope") is None
    assert metadata_store.find_by_content_hash("hash-1")["doc_id"] == "doc-a"


def test_list_documents_orders_by_creation(metadata_store: MetadataStore) -> None:
    metadata_store.add_document("doc-a", "A", "h1")
    metadata_store.add_document("doc-b", "B", "h2")

    rows = metadata_store.list_documents()
    assert [r["doc_id"] for r in rows] == ["doc-a", "doc-b"]