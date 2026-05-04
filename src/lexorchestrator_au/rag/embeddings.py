import hashlib
import math
from collections.abc import Sequence
from typing import Any

import httpx

from lexorchestrator_au.core.cache import AsyncCache
from lexorchestrator_au.core.config import Settings


class EmbeddingProvider:
    dimensions: int

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:  # pragma: no cover - interface
        raise NotImplementedError

    async def embed_query(self, text: str) -> list[float]:
        return (await self.embed_texts([text]))[0]


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding substitute for dev/test and air-gapped demos.

    It is not semantic-quality equivalent to provider embeddings, but it keeps ingestion and
    retrieval pipelines fully runnable without external keys.
    """

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
    def __init__(self, api_key: str, model: str, dimensions: int, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model = model
        self.dimensions = dimensions
        self.timeout_seconds = timeout_seconds

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        payload: dict[str, Any] = {
            "model": self.model,
            "input": list(texts),
            "dimensions": self.dimensions,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        items = sorted(data["data"], key=lambda item: item["index"])
        return [item["embedding"] for item in items]


class CachedEmbeddingProvider(EmbeddingProvider):
    def __init__(self, provider: EmbeddingProvider, cache: AsyncCache, ttl_seconds: int) -> None:
        self.provider = provider
        self.cache = cache
        self.ttl_seconds = ttl_seconds
        self.dimensions = provider.dimensions

    async def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        results: list[list[float] | None] = []
        misses: list[tuple[int, str, str]] = []
        for idx, text in enumerate(texts):
            key = self._cache_key(text)
            cached = await self.cache.get_json(key)
            if cached is None:
                results.append(None)
                misses.append((idx, key, text))
            else:
                results.append([float(value) for value in cached])

        if misses:
            embeddings = await self.provider.embed_texts([text for _, _, text in misses])
            for (idx, key, _), embedding in zip(misses, embeddings, strict=True):
                results[idx] = embedding
                await self.cache.set_json(key, embedding, self.ttl_seconds)
        return [embedding for embedding in results if embedding is not None]

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        return f"embedding:{self.provider.__class__.__name__}:{self.dimensions}:{digest}"


def build_embedding_provider(settings: Settings, cache: AsyncCache | None = None) -> EmbeddingProvider:
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        provider: EmbeddingProvider = OpenAIEmbeddingProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_embedding_model,
            dimensions=settings.embedding_dimensions,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    else:
        provider = HashEmbeddingProvider(dimensions=settings.embedding_dimensions)

    if cache is not None:
        return CachedEmbeddingProvider(provider, cache, settings.cache_ttl_seconds)
    return provider
