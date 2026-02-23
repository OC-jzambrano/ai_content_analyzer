from __future__ import annotations

from arq.connections import RedisSettings, create_pool
from app.core.config import settings

async def get_redis_pool():
    return await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))