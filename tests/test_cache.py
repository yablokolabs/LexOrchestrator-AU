from lexorchestrator_au.core.cache import InMemoryTTLCache, NullCache


class TestNullCache:
    async def test_always_returns_none(self) -> None:
        cache = NullCache()
        assert await cache.get_json("any") is None
        assert not await cache.is_healthy()


class TestInMemoryTTLCache:
    async def test_set_and_get(self) -> None:
        cache = InMemoryTTLCache()
        await cache.set_json("key", {"data": 1}, ttl_seconds=60)
        result = await cache.get_json("key")
        assert result == {"data": 1}

    async def test_miss_returns_none(self) -> None:
        cache = InMemoryTTLCache()
        assert await cache.get_json("missing") is None

    async def test_lru_eviction(self) -> None:
        cache = InMemoryTTLCache(max_entries=3)
        await cache.set_json("a", 1, ttl_seconds=60)
        await cache.set_json("b", 2, ttl_seconds=60)
        await cache.set_json("c", 3, ttl_seconds=60)
        await cache.set_json("d", 4, ttl_seconds=60)

        # "a" should have been evicted (oldest)
        assert await cache.get_json("a") is None
        assert await cache.get_json("d") == 4

    async def test_is_healthy(self) -> None:
        cache = InMemoryTTLCache()
        assert await cache.is_healthy()
