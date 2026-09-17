import os

import httpx
import pytest

BASE_URL = os.environ.get("AI_BACKEND_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("AI_BACKEND_KEY", "")


def _stack_reachable() -> bool:
    try:
        return httpx.get(f"{BASE_URL}/health", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _stack_reachable(), reason="live stack not reachable"),
]


def _headers() -> dict[str, str]:
    if not API_KEY:
        pytest.skip("AI_BACKEND_KEY not set")
    return {"Authorization": f"Bearer {API_KEY}"}


def _post(path: str, body: dict[str, object]) -> httpx.Response:
    return httpx.post(f"{BASE_URL}{path}", json=body, headers=_headers(), timeout=60)


def _get(path: str) -> httpx.Response:
    return httpx.get(f"{BASE_URL}{path}", headers=_headers(), timeout=10)


def test_health() -> None:
    response = httpx.get(f"{BASE_URL}/health", timeout=5)
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_embeddings_and_similarity() -> None:
    similarity = _post("/similarity", {"text_a": "hello", "text_b": "world"})
    assert similarity.status_code == 200
    body = similarity.json()
    assert -1.0 <= body["similarity"] <= 1.0


def test_chat_returns_response_and_model() -> None:
    chat = _post("/chat", {"message": "Say hi in one short sentence.", "max_tokens": 50})
    assert chat.status_code == 200
    body = chat.json()
    assert body["response"]
    assert body["model"]


def test_documents_metadata_lists_ingested_docs() -> None:
    response = _get("/documents/metadata")
    assert response.status_code == 200
    rows = response.json()
    assert isinstance(rows, list)


def test_search_returns_scored_documents() -> None:
    search = _post("/search", {"query": "RAG", "limit": 3})
    assert search.status_code == 200
    results = search.json()
    assert isinstance(results, list)
    assert all({"id", "text", "score"} <= r.keys() for r in results)


def test_unauthorized_request_is_rejected() -> None:
    response = httpx.post(
        f"{BASE_URL}/chat",
        json={"message": "hi"},
        timeout=10,
    )
    assert response.status_code == 401


def test_agent_graph_rejects_streaming() -> None:
    response = _post("/agent/graph", {"question": "hi", "stream": True})
    assert response.status_code == 400


def test_models_lists_seeded_registry() -> None:
    response = _get("/models")
    assert response.status_code == 200
    models = response.json()
    assert isinstance(models, list)
    assert len(models) >= 1
    assert {"id", "provider", "name"} <= models[0].keys()


def test_models_unknown_returns_404() -> None:
    response = _get("/models/does-not-exist")
    assert response.status_code == 404