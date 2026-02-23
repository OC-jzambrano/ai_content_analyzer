from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel

class SampledFrame(BaseModel):
    index: int
    timestamp_sec: float
    path: str

class MediaResult(BaseModel):
    post_id: str
    video_path: Optional[str] = None
    audio_path: Optional[str] = None
    frames: List[SampledFrame] = []