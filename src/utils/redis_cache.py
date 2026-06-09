import json
import os
from typing import Any, Optional

import redis.asyncio as redis

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    _redis_client = redis.from_url(redis_url, decode_responses=True)
    return _redis_client


async def get_cached_json(redis_client: redis.Redis, key: str) -> Optional[Any]:
    raw_value = await redis_client.get(key)
    if raw_value is None:
        return None
    try:
        return json.loads(raw_value)
    except json.JSONDecodeError:
        return None


async def set_cached_json(redis_client: redis.Redis, key: str, data: Any, expire: int = 30) -> None:
    payload = json.dumps(data, ensure_ascii=False)
    await redis_client.set(key, payload, ex=expire)
