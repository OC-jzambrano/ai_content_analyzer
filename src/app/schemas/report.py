from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

class CategoryAggregate(BaseModel):
    category: str
    average_safety_score: float
    status: str

class OverallScore(BaseModel):
    score: float
    status: str

class CampaignReport(BaseModel):
    campaign_id: str

    visual_categories: List[CategoryAggregate]
    text_categories: List[CategoryAggregate]

    overall_visual: OverallScore
    overall_text: OverallScore

    summary: str

    posts: List[PostProcessingResult]
    partial_failure_count: int

class PostProcessingResult(BaseModel):
    post_id: str
    success: bool
    error_stage: Optional[str] = None
    error_message: Optional[str] = None