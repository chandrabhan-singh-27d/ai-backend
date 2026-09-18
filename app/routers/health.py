import json

from fastapi import APIRouter, Response

from app.services.job_store import get_job_store
from app.services.vector_store import get_store

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready")
def readiness() -> Response:
    checks: dict[str, bool] = {}
    try:
        get_store().count()
        checks["qdrant"] = True
    except Exception:
        checks["qdrant"] = False
    try:
        get_job_store().list(limit=1)
        checks["sqlite"] = True
    except Exception:
        checks["sqlite"] = False

    ready = all(checks.values())
    body = json.dumps({"status": "ready" if ready else "not_ready", **checks})
    return Response(
        content=body,
        status_code=200 if ready else 503,
        media_type="application/json",
    )