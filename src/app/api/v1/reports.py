from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

from src.app.core.config import settings
from src.app.services.report_store import ReportStore

router = APIRouter(prefix="/v1", tags=["reports"])  

class CampaignReportResponse(BaseModel):
    campaign_id: str
    summary: Optional[str] = None
    overall: Optional[Dict[str, Any]] = None
    categories: Optional[Dict[str, Any]] = None
    posts_analyzed: int = 0
    partial_failures: bool = False

@router.get("/campaigns/{campaign_id}/report")
async def get_report(campaign_id: str):
    store = ReportStore(settings.REDIS_URL)
    report = await store.get(campaign_id)
    if not report:
        raise HTTPException(status_code=404, detail="report_not_found")
    return report