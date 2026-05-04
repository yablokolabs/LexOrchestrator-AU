import asyncio
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_DEFAULT_MAX_ENTRIES = 10_000


class AsyncCache:
    async def get_json(self, key: str) -> Any | None:  # pragma: no cover - interface
        raise NotImplementedError

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:  # pragma: no cover
        raise NotImplementedError

    async def close(self) -> None:
        return None

    async def is_healthy(self) -> bool:
        return True


class NullCache(AsyncCache):
    async def get_json(self, key: str) -> Any | None:
        return None

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        return None

    async def is_healthy(self) -> bool:
        return False


class InMemoryTTLCache(AsyncCache):
    def __init__(self, max_entries: int = _DEFAULT_MAX_ENTRIES) -> None:
        self._values: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_entries = max_entries

    async def get_json(self, key: str) -> Any | None:
        async with self._lock:
            item = self._values.get(key)
            if not item:
                return None
            expires_at, value = item
            if expires_at < time.monotonic():
                self._values.pop(key, None)
                return None
            self._values.move_to_end(key)
            return value

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        async with self._lock:
            self._values[key] = (time.monotonic() + ttl_seconds, value)
            self._values.move_to_end(key)
            while len(self._values) > self._max_entries:
                self._values.popitem(last=False)


class RedisTTLCache(AsyncCache):
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def get_json(self, key: str) -> Any | None:
        raw = await self._redis.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_json(self, key: str, value: Any, ttl_seconds: int) -> None:
        await self._redis.set(key, json.dumps(value), ex=ttl_seconds)

    async def close(self) -> None:
        await self._redis.aclose()

    async def is_healthy(self) -> bool:
        try:
            result: bool = await self._redis.ping()
            return result
        except Exception:
            return False


async def create_cache(
    redis_url: str | None, max_entries: int = _DEFAULT_MAX_ENTRIES
) -> AsyncCache:
    if not redis_url:
        return InMemoryTTLCache(max_entries=max_entries)
    try:
        redis = Redis.from_url(redis_url, encoding="utf-8", decode_responses=True)
        await redis.ping()
        logger.info("redis_cache_connected", extra={"url": redis_url.split("@")[-1]})
        return RedisTTLCache(redis)
    except Exception:
        logger.warning(
            "redis_unavailable_falling_back_to_in_memory_cache",
            extra={"url": redis_url.split("@")[-1]},
        )
        return InMemoryTTLCache(max_entries=max_entries)


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
