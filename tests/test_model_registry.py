import pytest

from app.services.model_registry import ModelStore


@pytest.fixture
def model_store(tmp_path) -> ModelStore:
    return ModelStore(db_path=str(tmp_path / "models.db"))


def test_create_and_get(model_store: ModelStore) -> None:
    model_store.create("gpt-4o", "openai", "GPT-4o")

    assert model_store.get("gpt-4o") == {"id": "gpt-4o", "provider": "openai", "name": "GPT-4o"}


def test_get_unknown_returns_none(model_store: ModelStore) -> None:
    assert model_store.get("does-not-exist") is None


def test_list_filters_by_provider(model_store: ModelStore) -> None:
    model_store.create("a", "openai", "A")
    model_store.create("b", "groq", "B")

    assert [m["id"] for m in model_store.list()] == ["a", "b"]
    assert [m["id"] for m in model_store.list("groq")] == ["b"]
    assert [m["id"] for m in model_store.list("anthropic")] == []


def test_create_is_idempotent(model_store: ModelStore) -> None:
    model_store.create("a", "openai", "A")
    model_store.create("a", "openai", "A2")

    assert model_store.count() == 1
    assert model_store.get("a")["name"] == "A2"