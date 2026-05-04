import time
from typing import Any

import httpx

from lexorchestrator_au.adapters.base import (
    AdapterError,
    APIDriftError,
    LLMRequest,
    LLMResponse,
    NonRetryableError,
    ProviderUnavailable,
)


class OpenAIChatAdapterV1:
    name = "openai"
    version = "2024-compat-chat-completions"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout_seconds,
                headers={"Authorization": f"Bearer {self.api_key}"},
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            )
        return self._client

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise ProviderUnavailable("OPENAI_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        client = await self._get_client()
        start = time.perf_counter()
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                json=payload,
            )
        except httpx.TimeoutException as exc:
            raise AdapterError(f"OpenAI request timed out: {exc}") from exc

        self._handle_http_error(response)
        data = response.json()

        try:
            choice = data["choices"][0]
            message = choice.get("message", {})
            answer = message.get("content")
            finish_reason = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError) as exc:
            raise APIDriftError(f"Unexpected OpenAI response: {data!r}") from exc

        if not isinstance(answer, str) or not answer.strip():
            raise APIDriftError("OpenAI returned no textual content")

        usage = data.get("usage") or {}
        return LLMResponse(
            answer=answer.strip(),
            provider=self.name,
            model=self.model,
            raw={"id": data.get("id"), "adapter_version": self.version},
            token_usage={
                k: int(v)
                for k, v in usage.items()
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            },
            latency_ms=(time.perf_counter() - start) * 1000,
            finish_reason=finish_reason,
        )

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    @staticmethod
    def _handle_http_error(response: httpx.Response) -> None:
        if response.is_success:
            return
        status = response.status_code
        if 400 <= status < 500 and status != 429:
            raise NonRetryableError(f"OpenAI returned {status}: {response.text[:300]}")
        response.raise_for_status()
