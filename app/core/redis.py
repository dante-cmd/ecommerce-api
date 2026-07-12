from typing import AsyncGenerator

import redis.asyncio as redis

from app.core.config import Settings, get_settings

_pool: redis.Redis | None = None


def get_redis_pool(settings: Settings) -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.Redis.from_url(str(settings.redis_url), decode_responses=True)
    return _pool


async def get_redis() -> AsyncGenerator[redis.Redis, None]:
    settings = get_settings()
    client = get_redis_pool(settings)
    try:
        yield client
    finally:
        pass


async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
