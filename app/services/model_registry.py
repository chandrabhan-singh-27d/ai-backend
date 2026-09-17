import os
import sqlite3
from datetime import UTC, datetime
from typing import cast

_SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,
    provider    TEXT NOT NULL,
    name        TEXT NOT NULL,
    created_at  TEXT NOT NULL
)
"""


class ModelStore:
    def __init__(self, db_path: str = "data/models.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def create(self, model_id: str, provider: str, name: str) -> dict[str, str]:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO models (id, provider, name, created_at) "
                "VALUES (?, ?, ?, ?)",
                (model_id, provider, name, datetime.now(UTC).isoformat()),
            )
        return {"id": model_id, "provider": provider, "name": name}

    def get(self, model_id: str) -> dict[str, str] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, provider, name FROM models WHERE id = ?", (model_id,)
            ).fetchone()
        return cast("dict[str, str] | None", dict(row)) if row else None

    def list(self, provider: str | None = None) -> list[dict[str, str]]:
        query = "SELECT id, provider, name FROM models"
        params: tuple[str, ...] = ()
        if provider is not None:
            query += " WHERE provider = ?"
            params = (provider,)
        query += " ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [cast("dict[str, str]", dict(row)) for row in rows]

    def count(self) -> int:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM models").fetchone()
        return int(count[0])


_model_store: ModelStore | None = None


def get_model_store() -> ModelStore:
    global _model_store
    if _model_store is None:
        from app.config import MODELS_DB_PATH

        store = ModelStore(db_path=MODELS_DB_PATH)
        if store.count() == 0:
            _seed_defaults(store)
        _model_store = store
    return _model_store


def _seed_defaults(store: ModelStore) -> None:
    from app.config import EVAL_JUDGE_MODEL, LLM_MODEL

    for model in (LLM_MODEL, EVAL_JUDGE_MODEL):
        provider = model.split("/", 1)[0] if "/" in model else "groq"
        store.create(model, provider, model)