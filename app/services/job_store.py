import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from typing import TypedDict, cast

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs(
    id              TEXT PRIMARY KEY,
    kind            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    payload         TEXT NOT NULL,
    result          TEXT,
    error           TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL,
    started_at      TEXT,
    finished_at     TEXT
)
"""


class Job(TypedDict):
    id: str
    kind: str
    payload: dict[str, object]
    attempts: int


class JobStore:
    def __init__(self, db_path: str = "data/jobs.db") -> None:
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        with self._connect() as conn:
            conn.execute(_SCHEMA)
            self._migrate(conn)

    def _migrate(self, conn: sqlite3.Connection) -> None:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if "attempts" not in columns:
            conn.execute("ALTER TABLE jobs ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0")

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

    def _reclaim_stale(self, conn: sqlite3.Connection, heartbeat_timeout_seconds: int) -> None:
        threshold = (datetime.now(UTC) - timedelta(seconds=heartbeat_timeout_seconds)).isoformat()
        conn.execute(
            "UPDATE jobs SET status = 'pending', started_at = NULL "
            "WHERE status = 'running' AND started_at < ?",
            (threshold,),
        )

    def claim(self, heartbeat_timeout_seconds: int | None = None) -> Job | None:
        if heartbeat_timeout_seconds is None:
            from app.config import JOB_HEARTBEAT_TIMEOUT_SECONDS

            heartbeat_timeout_seconds = JOB_HEARTBEAT_TIMEOUT_SECONDS
        with self._connect() as conn:
            self._reclaim_stale(conn, heartbeat_timeout_seconds)
            row = conn.execute(
                "SELECT id, kind, payload, attempts FROM jobs "
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
                "SELECT id, kind, status, payload, result, error, attempts, "
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

    def list(self, limit: int = 20, offset: int = 0) -> list[dict[str, object]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, kind, status, payload, result, error, attempts, "
                "created_at, started_at, finished_at FROM jobs "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (max(1, min(limit, 100)), max(0, offset)),
            ).fetchall()
        jobs: list[dict[str, object]] = []
        for row in rows:
            job = dict(row)
            job["payload"] = json.loads(job["payload"])
            if job["result"] is not None:
                job["result"] = json.loads(job["result"])
            jobs.append(job)
        return jobs

    def complete(self, job_id: str, result: dict[str, object]) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'succeeded', result = ?, finished_at = ? WHERE id = ?",
                (json.dumps(result), datetime.now(UTC).isoformat(), job_id),
            )

    def requeue(self, job_id: str, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'pending', error = ?, started_at = NULL, "
                "attempts = attempts + 1 WHERE id = ?",
                (error, job_id),
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
        from app.config import JOBS_DB_PATH

        _job_store = JobStore(db_path=JOBS_DB_PATH)
    return _job_store