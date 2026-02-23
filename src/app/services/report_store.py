from __future__ import annotations

import json
from typing import Optional

import redis.asyncio as redis

from src.app.schemas.report import CampaignReport


class ReportStore:
    def __init__(self, redis_url: str, prefix: str = "reports:") -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._prefix = prefix

    def _key(self, campaign_id: str) -> str:
        return f"{self._prefix}{campaign_id}"

    async def set(self, report: CampaignReport) -> None:
        await self._redis.set(self._key(report.campaign_id), report.model_dump_json())

    async def get(self, campaign_id: str) -> Optional[CampaignReport]:
        raw = await self._redis.get(self._key(campaign_id))
        if not raw:
            return None
        return CampaignReport(**json.loads(raw))