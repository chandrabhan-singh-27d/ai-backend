import os

os.environ.setdefault("OTEL_TRACING_ENABLED", "false")

import pytest


@pytest.fixture
def keys_store(tmp_path):
    from app.services.api_keys import ApiKeysStore

    return ApiKeysStore(db_path=str(tmp_path / "keys.db"))


@pytest.fixture
def job_store(tmp_path):
    from app.services.job_store import JobStore

    return JobStore(db_path=str(tmp_path / "jobs.db"))


@pytest.fixture
def vector_store():
    from qdrant_client import QdrantClient

    from app.services.vector_store import VectorStore

    return VectorStore(
        client=QdrantClient(path=":memory:"),
        collection="test_documents",
        vector_size=3,
    )