from pydantic import BaseModel
from typing import Any, Dict, List, Optional

class CategoryScore(BaseModel):
    category: str
    safety_score: Optional[float]  # 0..100, None if not evaluated
    status: str  # Safe | Warning | Unsafe
    explanation: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class VisualModerationSchema(BaseModel):
    adult_content: CategoryScore
    violence_weapons: CategoryScore
    racy_content: CategoryScore
    medical_gore: CategoryScore
    spoof_fake: CategoryScore

class TextModerationSchema(BaseModel):
    profanity: CategoryScore
    hate_speech: CategoryScore
    misinformation: CategoryScore
    brand_mentions: CategoryScore
    disclosure_compliance: CategoryScore
    political_content: CategoryScore

class PostModerationResult(BaseModel):
    post_id: str
    visual: Optional[VisualModerationSchema] = None
    text: Optional[TextModerationSchema] = None
    errors: list[str] = []

class VisualModerationResult(BaseModel):
    post_id: str
    categories: List[CategoryScore]
    frame_count: int
    partial_failures: List[str] = []  # list of frame paths that failed

class TextModerationResult(BaseModel):
    post_id: str
    categories: List[CategoryScore]
    language: str = "en"