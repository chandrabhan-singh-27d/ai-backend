from app.services.vector_store import VectorStore


def test_add_get_exists_count(vector_store: VectorStore) -> None:
    vector_store.add("doc-1", "hello world", [1.0, 0.0, 0.0])

    assert vector_store.get("doc-1") == "hello world"
    assert vector_store.exists("doc-1") is True
    assert vector_store.count() == 1


def test_search_ranks_by_similarity(vector_store: VectorStore) -> None:
    vector_store.add("doc-a", "python", [1.0, 0.0, 0.0])
    vector_store.add("doc-b", "database", [0.0, 1.0, 0.0])

    results = vector_store.search([1.0, 0.0, 0.0], top_k=2)
    assert [r["id"] for r in results] == ["doc-a", "doc-b"]
    assert results[0]["score"] > results[1]["score"]


def test_delete_removes_document(vector_store: VectorStore) -> None:
    vector_store.add("doc-1", "hello", [1.0, 0.0, 0.0])
    vector_store.delete("doc-1")

    assert vector_store.exists("doc-1") is False
    assert vector_store.get("doc-1") is None
    assert vector_store.count() == 0


def test_duplicate_doc_id_overwrites(vector_store: VectorStore) -> None:
    vector_store.add("doc-1", "first", [1.0, 0.0, 0.0])
    vector_store.add("doc-1", "second", [1.0, 0.0, 0.0])

    assert vector_store.get("doc-1") == "second"
    assert vector_store.count() == 1


def test_list_all_returns_all_documents(vector_store: VectorStore) -> None:
    vector_store.add("doc-1", "hello", [1.0, 0.0, 0.0])
    vector_store.add("doc-2", "world", [0.0, 1.0, 0.0])

    docs = vector_store.list_all()
    assert {d["id"] for d in docs} == {"doc-1", "doc-2"}
    assert all({"id", "text"} <= d.keys() for d in docs)