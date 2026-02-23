from pydantic import BaseModel, Field
from typing import List, Optional

class PostSchema(BaseModel):
    platform_post_id: str
    url: str
    weight: float = Field(default=1.0, ge=0)

class CampaignInputSchema(BaseModel):
    platform: str = Field(..., examples=["tiktok", "instagram"])
    creator_handle: str
    posts: List[PostSchema]
    options: Optional[dict] = None