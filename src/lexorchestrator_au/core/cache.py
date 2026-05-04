import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis


class AsyncCache:
    async def get_json(self, key: str) -> Any | None:  # pragma: no cover - interface
        raise NotImplementedError

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:
        return None


class NullCache(AsyncCache):
    async def get_json(self, key: str) -> Any | None:
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None


class InMemoryTTLCache(AsyncCache):
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, Any]] = {}
        self._lock = asyncio.Lock()

    async def get_json(self, key: str) -> Any | None:
        async with self._lock:
            item = self._values.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.monotonic():
                self._values.pop(key, None)
                return None
            return value

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            self._values[key] = (time.monotonic() + ttl_seconds, value)


class RedisTTLCache(AsyncCache):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_json(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl_seconds)

    async def close(self) -> None:
        await self._redis.aclose()


async def create_cache(redis_url: str | None) -> AsyncCache:
    if not redis_url:
        return InMemoryTTLCache()
    try:
        redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await redis.ping()
        return RedisTTLCache(redis)
    except Exception:
        return InMemoryTTLCache()


async def get_or_set_json(
    cache: AsyncCache,
    key: str,
    ttl_seconds: int,
    factory: Callable[[], Awaitable[Any]],
) -> Any:
    cached = await cache.get_json(key)
    if cached is not None:
        return cached
    value = await factory()
    await cache.set_json(key, value, ttl_seconds)
    return value
