import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from typing import TypedDict, cast

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    payload         TEXT NOT NULL,
    result          TEXT,
    error           TEXT,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT
)
"""


class Job(TypedDict):
    id: str
    kind: str
    payload: dict[str, object]


class JobStore:
    def __init__(self, db_path: str = "data/jobs.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def create(self, kind: str, payload: dict[str, object]) -> str:
        job_id = uuid.uuid4().hex
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO jobs (id, kind, payload, created_at) VALUES (?, ?, ?, ?)",
                (job_id, kind, json.dumps(payload), datetime.now(UTC).isoformat()),
            )
        return job_id

    def claim(self) -> Job | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, kind, payload FROM jobs "
                "WHERE status = 'pending' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            cur = conn.execute(
                "UPDATE jobs SET "
                "status = 'running', started_at = ? "
                "WHERE id = ? AND status = 'pending'",
                (datetime.now(UTC).isoformat(), row["id"]),
            )
            if cur.rowcount == 0:
                return None
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        return cast(Job, job)

    def get(self, job_id: str) -> dict[str, object] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, kind, status, payload, result, error, "
                "created_at, started_at, finished_at FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        if row is None:
            return None
        job = dict(row)
        job["payload"] = json.loads(job["payload"])
        if job["result"] is not None:
            job["result"] = json.loads(job["result"])
        return job

    def complete(self, job_id: str, result: dict[str, object]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'succeeded', result = ?, finished_at = ? WHERE id = ?",
                (json.dumps(result), datetime.now(UTC).isoformat(), job_id),
            )

    def fail(self, job_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'failed', error = ?, finished_at = ? WHERE id = ?",
                (error, datetime.now(UTC).isoformat(), job_id),
            )


_job_store: JobStore | None = None


def get_job_store() -> JobStore:
    global _job_store
    if _job_store is None:
        _job_store = JobStore()
    return _job_store
