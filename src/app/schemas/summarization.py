from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel

class PolicySignal(BaseModel):
    category: str  # Brand Mentions, Disclosure Compliance, Misinformation, Political Content
    safety_score: Optional[float]  # 0..100, None if unknown
    status: str  # Safe | Warning | Unsafe
    explanation: Optional[str] = None
    recommendation: Optional[str] = None


class SummarizationResult(BaseModel):
    post_id: str
    summary: str
    key_points: List[str] = []
    signals: List[PolicySignal] = []