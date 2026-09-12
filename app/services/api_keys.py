import hashlib
import os
import secrets
import sqlite3
from datetime import UTC, datetime
from typing import cast

PREFIX = "ak_live_"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS api_keys(
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    prefix          TEXT NOT NULL,
    key_hash        TEXT NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    revoked         INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL
)
"""


def generate_key() -> str:
    return PREFIX + secrets.token_hex(16)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


class ApiKeysStore:
    def __init__(self, db_path: str = "data/keys.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def create(self, name: str) -> str:
        key = generate_key()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO api_keys (prefix, key_hash, name, created_at) VALUES (?, ?, ?, ?)",
                (PREFIX, hash_key(key), name, datetime.now(UTC).isoformat()),
            )
        return key

    def find(self, key: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, name, revoked, created_at FROM api_keys "
                "WHERE key_hash = ? AND revoked = 0",
                (hash_key(key),),
            ).fetchone()
        return cast("dict[str, object] | None", dict(row)) if row else None

    def list_all(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, name, prefix, revoked, created_at, "
                "substr(key_hash, 1, 8) AS fingerprint "
                "FROM api_keys ORDER BY id"
            ).fetchall()
        return [cast("dict[str, object]", dict(row)) for row in rows]

    def revoke(self, key_id: int) -> None:
        with self._connect() as conn:
            conn.execute("UPDATE api_keys SET revoked = 1 WHERE id = ?", (key_id,))


_api_keys_store: ApiKeysStore | None = None


def get_api_keys_store() -> ApiKeysStore:
    global _api_keys_store
    if _api_keys_store is None:
        _api_keys_store = ApiKeysStore()
    return _api_keys_store
