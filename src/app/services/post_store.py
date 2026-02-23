from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as redis


class PostResultStore:
    """
    Stores per-post full result blob.
    Key pattern:
        posts:{campaign_id}:{post_id}
    """

    def __init__(self, redis_url: str, prefix: str = "posts:") -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix

    def _key(self, campaign_id: str, post_id: str) -> str:
        return f"{self._prefix}{campaign_id}:{post_id}"

    async def set(self, campaign_id: str, post_id: str, data: dict) -> None:
        await self._redis.set(self._key(campaign_id, post_id), json.dumps(data))

    async def get(self, campaign_id: str, post_id: str) -> Optional[dict]:
        raw = await self._redis.get(self._key(campaign_id, post_id))
        if not raw:
            return None
        return json.loads(raw)