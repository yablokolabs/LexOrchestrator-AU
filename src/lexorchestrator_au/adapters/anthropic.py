import time
from typing import Any

import httpx

from lexorchestrator_au.adapters.base import (
    APIDriftError,
    LLMRequest,
    LLMResponse,
    ProviderUnavailable,
)


class AnthropicMessagesAdapterV1:
    name = "anthropic"
    version = "2023-06-01-messages"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise ProviderUnavailable("ANTHROPIC_API_KEY is not configured")

        payload: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 1200,
            "temperature": 0.1,
            "system": request.system_prompt,
            "messages": [{"role": "user", "content": request.user_prompt}],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        try:
            parts = data["content"]
            answer = "\n".join(part.get("text", "") for part in parts if part.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise APIDriftError(f"Unexpected Anthropic response: {data!r}") from exc

        if not answer.strip():
            raise APIDriftError("Anthropic returned no textual content")

        usage = data.get("usage") or {}
        return LLMResponse(
            answer=answer.strip(),
            provider=self.name,
            model=self.model,
            raw={"id": data.get("id"), "adapter_version": self.version},
            token_usage={k: int(v) for k, v in usage.items() if isinstance(v, int)},
            latency_ms=(time.perf_counter() - start) * 1000,
            finish_reason=data.get("stop_reason"),
        )
