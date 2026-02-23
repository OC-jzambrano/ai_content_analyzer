from pydantic import BaseModel
from typing import Literal, Optional

class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    result: Optional[dict] = None
    error: Optional[str] = None