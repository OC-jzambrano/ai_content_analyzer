from __future__ import annotations

import json
from typing import Optional, Dict, Any

import redis.asyncio as redis


class JobStore:
    def __init__(self, redis_url: str, prefix: str = "jobs:") -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix

    def _key(self, job_id: str) -> str:
        return f"{self._prefix}{job_id}"

    async def set(self, status: Dict[str, Any]) -> None:
        """
        Expects a plain dict representing job status.
        Example:
        {
            "job_id": "...",
            "status": "queued|running|done|failed",
            "result": {...} | None,
            "error": "..." | None
        }
        """
        await self._redis.set(
        self._key(status.job_id),
        json.dumps(status.model_dump())
    )

    async def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        raw = await self._redis.get(self._key(job_id))
        if not raw:
            return None
        return json.loads(raw)