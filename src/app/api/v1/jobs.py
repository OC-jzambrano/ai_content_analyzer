from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.app.core.config import settings
from src.app.services.job_store import JobStore
from src.app.schemas.jobs import JobStatusResponse

router = APIRouter(prefix="/v1", tags=["jobs"])

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str) -> JobStatusResponse:
    store = JobStore(settings.REDIS_URL)

    data = await store.get(job_id)
    if not data:
        raise HTTPException(status_code=404, detail="job_not_found")

    return JobStatusResponse(**data)