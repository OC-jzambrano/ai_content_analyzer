from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, HttpUrl

class IngestedPost(BaseModel):
    post_id: str
    url: Optional[HttpUrl] = None
    caption: Optional[str] = None
    media_urls: List[HttpUrl] = []

class IngestionResult(BaseModel):
    campaign_id: str
    posts: List[IngestedPost]