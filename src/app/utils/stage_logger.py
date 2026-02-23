import time
from typing import Optional
from src.app.core.logging import get_logger

logger = get_logger("pipeline")


class StageTimer:
    def __init__(self, job_id: str, post_id: Optional[str], stage: str):
        self.job_id = job_id
        self.post_id = post_id
        self.stage = stage
        self.start = time.perf_counter()

    def log(self, success: bool, retry_count: int = 0):
        latency_ms = round((time.perf_counter() - self.start) * 1000, 2)

        logger.info(
            "stage_completed",
            extra={
                "extra_data": {
                    "job_id": self.job_id,
                    "post_id": self.post_id,
                    "stage": self.stage,
                    "latency_ms": latency_ms,
                    "success": success,
                    "retry_count": retry_count,
                }
            },
        )