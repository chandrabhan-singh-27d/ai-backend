from fastapi import APIRouter, HTTPException

from app.dependencies import PROTECTED
from app.services.job_store import get_job_store

router = APIRouter(dependencies=PROTECTED)


@router.get("/jobs")
def list_jobs(limit: int = 20) -> list[dict[str, object]]:
    return get_job_store().list(limit)


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    job = get_job_store().get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job