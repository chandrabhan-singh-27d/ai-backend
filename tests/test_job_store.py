from app.services.job_store import JobStore


def test_create_claim_complete_lifecycle(job_store: JobStore) -> None:
    job_id = job_store.create("ingest_document", {"id": "doc-1"})

    claimed = job_store.claim()
    assert claimed is not None
    assert claimed["id"] == job_id
    assert claimed["payload"] == {"id": "doc-1"}

    job_store.complete(job_id, {"status": "ok", "id": "doc-1"})
    job = job_store.get(job_id)
    assert job is not None
    assert job["status"] == "succeeded"
    assert job["result"] == {"status": "ok", "id": "doc-1"}
    assert job["started_at"] is not None
    assert job["finished_at"] is not None


def test_job_is_claimed_only_once(job_store: JobStore) -> None:
    job_store.create("ingest_document", {"id": "doc-1"})

    first = job_store.claim()
    second = job_store.claim()
    assert first is not None
    assert second is None


def test_fail_records_error(job_store: JobStore) -> None:
    job_id = job_store.create("ingest_document", {"id": "doc-1"})
    job_store.claim()
    job_store.fail(job_id, "embedding failed")

    job = job_store.get(job_id)
    assert job is not None
    assert job["status"] == "failed"
    assert job["error"] == "embedding failed"


def test_payload_round_trips_nested_dicts(job_store: JobStore) -> None:
    payload = {"id": "doc-1", "metadata": {"source": "smoke", "nested": [1, 2, 3]}}
    job_store.create("ingest_document", payload)

    claimed = job_store.claim()
    assert claimed is not None
    assert claimed["payload"] == payload


def test_get_unknown_job_returns_none(job_store: JobStore) -> None:
    assert job_store.get("does-not-exist") is None