from fastapi import APIRouter, HTTPException, Query

from app.dependencies import PROTECTED
from app.services.job_store import get_job_store

router = APIRouter(dependencies=PROTECTED)


@router.get("/jobs")
def list_jobs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    return get_job_store().list(limit, offset)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job