from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class TranscriptSegment(BaseModel):
    start_ms: int
    end_ms: int
    text: str


class TranscriptionResult(BaseModel):
    post_id: str
    transcript_text: str
    segments: List[TranscriptSegment] = []
    provider: str = "assemblyai"
    provider_job_id: Optional[str] = None
    confidence: Optional[float] = None