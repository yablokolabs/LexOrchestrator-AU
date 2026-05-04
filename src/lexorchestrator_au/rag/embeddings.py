import hashlib
import logging
import math
from collections.abc import Sequence
from typing import Any

import httpx

from lexorchestrator_au.core.cache import AsyncCache
from lexorchestrator_au.core.config import Settings

logger = logging.getLogger(__name__)

_OPENAI_MAX_BATCH = 2048
_RETRY_ATTEMPTS = 3
_RETRY_BASE_DELAY = 1.0


class EmbeddingProvider:
    dimensions: int

    async def embed_texts(
        self, texts: Sequence[str]
    ) -> list[list[float]]:  # pragma: no cover - interface
        raise NotImplementedError

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]

    async def aclose(self) -> None:
        pass


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding substitute for dev/test and air-gapped demos."""

    def __init__(self, dimensions: int = 384) -> None:
        self.dimensions = dimensions

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().split():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [round(value / norm, 8) for value in vector]


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        dimensions: int,
        timeout_seconds: float,
        max_batch: int = _OPENAI_MAX_BATCH,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds
        self.max_batch = max_batch
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"Authorization": f"Bearer {self.api_key}"},
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        text_list = list(texts)
        for start in range(0, len(text_list), self.max_batch):
            batch = text_list[start : start + self.max_batch]
            embeddings = await self._embed_batch_with_retry(batch)
            all_embeddings.extend(embeddings)
        return all_embeddings

    async def _embed_batch_with_retry(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(1, _RETRY_ATTEMPTS + 1):
            try:
                return await self._embed_batch(texts)
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in (429, 500, 502, 503):
                    delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    logger.warning(
                        "openai_embedding_retry",
                        extra={"attempt": attempt, "status": exc.response.status_code},
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                logger.warning(
                    "openai_embedding_retry", extra={"attempt": attempt, "error": str(exc)[:200]}
                )
                await asyncio.sleep(delay)
        raise RuntimeError(
            f"OpenAI embedding failed after {_RETRY_ATTEMPTS} attempts"
        ) from last_exc

    async def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": texts,
            "dimensions": self.dimensions,
        }
        client = await self._get_client()
        response = await client.post("https://api.openai.com/v1/embeddings", json=payload)
        response.raise_for_status()
        data = response.json()
        items = sorted(data["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


class CachedEmbeddingProvider(EmbeddingProvider):
    def __init__(self, provider: EmbeddingProvider, cache: AsyncCache, ttl_seconds: int) -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.dimensions = provider.dimensions

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float] | None] = [None] * len(texts)
        misses: list[tuple[int, str, str]] = []
        for idx, text in enumerate(texts):
            key = self._cache_key(text)
            cached = await self.cache.get_json(key)
            if cached is None:
                misses.append((idx, key, text))
            else:
                results[idx] = [float(value) for value in cached]

        if misses:
            embeddings = await self.provider.embed_texts([text for _, _, text in misses])
            for (idx, key, _), embedding in zip(misses, embeddings, strict=True):
                results[idx] = embedding
                await self.cache.set_json(key, embedding, self.ttl_seconds)

        if not all(e is not None for e in results):
            raise RuntimeError("CachedEmbeddingProvider: some embeddings are still None")
        return [e for e in results if e is not None]

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"embedding:{self.provider.__class__.__name__}:{self.dimensions}:{digest}"

    async def aclose(self) -> None:
        await self.provider.aclose()


def build_embedding_provider(
    settings: Settings, cache: AsyncCache | None = None
) -> EmbeddingProvider:
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        provider: EmbeddingProvider = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
            max_batch=settings.openai_embedding_max_batch,
        )
    else:
        provider = HashEmbeddingProvider(dimensions=settings.embedding_dimensions)

    if cache is not None:
        return CachedEmbeddingProvider(provider, cache, settings.cache_ttl_seconds)
    return provider
