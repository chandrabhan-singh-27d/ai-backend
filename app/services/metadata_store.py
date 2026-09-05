import os
import sqlite3
from datetime import UTC, datetime
from typing import cast

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id          TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    source          TEXT NOT NULL DEFAULT 'unknown',
    content_hash    TEXT NOT NULL,
    chunk_count     INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL
)
"""


class MetadataStore:
    def __init__(self, db_path: str = "data/app.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def add_document(
        self,
        doc_id: str,
        title: str,
        content_hash: str,
        source: str = "unknown",
        chunk_count: int = 1,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO documents "
                "(doc_id, title, source, content_hash, chunk_count, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (doc_id, title, source, content_hash, chunk_count, datetime.now(UTC).isoformat()),
            )

    def get_document(self, doc_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT doc_id, title, source, content_hash, chunk_count, created_at "
                "FROM documents WHERE doc_id = ?",
                (doc_id,),
            ).fetchone()
        return cast("dict[str, object] | None", dict(row)) if row else None

    def list_documents(self) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT doc_id, title, source, content_hash, chunk_count, created_at "
                "FROM documents ORDER BY created_at"
            ).fetchall()
        return [cast("dict[str, object]", dict(row)) for row in rows]

    def delete_document(self, doc_id: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM documents WHERE doc_id = ?", (doc_id,))

    def document_exists(self, doc_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
        return row is not None

    def count(self) -> int:
        with self._connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()
        return int(count[0])


_metadata_store: MetadataStore | None = None


def get_metadata_store() -> MetadataStore:
    global _metadata_store
    if _metadata_store is None:
        _metadata_store = MetadataStore()
    return _metadata_store
