from __future__ import annotations

import uuid
from fastapi import APIRouter

from pydantic import BaseModel, Field
from typing import List, Optional

from src.app.core.config import settings
from src.app.schemas.campaign import CampaignInputSchema
from src.app.api.v1.jobs import JobStatusResponse
from src.app.services.job_store import JobStore
from src.app.utils.arq import get_redis_pool

router = APIRouter(prefix="/v1", tags=["analysis"])

# Temporary schemas (we’ll replace with your real schemas in Step 5)
class PostInput(BaseModel):
    platform_post_id: str
    url: str
    weight: float = 1.0

class AnalyzeRequest(BaseModel):
    platform: str = Field(..., examples=["tiktok", "instagram"])
    creator_handle: str
    posts: List[PostInput]
    options: Optional[dict] = None

class JobResponse(BaseModel):
    job_id: str
    campaign_id: str
    status: str = "queued"

@router.post("/campaigns/{campaign_id}/analyze")
async def analyze_campaign(campaign_id: str, payload: CampaignInputSchema):
    job_id = uuid.uuid4().hex

    # store initial status
    job_store = JobStore(settings.REDIS_URL)
    await job_store.set(
        JobStatusResponse(
            job_id=job_id,
            campaign_id=campaign_id,
            status="queued",
            stage="queued",
        )
    )

    # enqueue background job
    redis = await get_redis_pool()
    await redis.enqueue_job(
    "src.app.workers.tasks.process_campaign",
    job_id,
    campaign_id,
    payload.model_dump(),
)

    return {"job_id": job_id, "campaign_id": campaign_id}