from __future__ import annotations

from arq.connections import ArqRedis, create_pool
from src.app.core.config import settings


async def get_redis_pool() -> ArqRedis:
    return await create_pool(settings.REDIS_URL)