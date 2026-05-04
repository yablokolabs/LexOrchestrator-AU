import time
from typing import Any

import httpx

from lexorchestrator_au.adapters.base import (
    APIDriftError,
    LLMRequest,
    LLMResponse,
    ProviderUnavailable,
)


class OpenAIChatAdapterV1:
    name = "openai"
    version = "2024-compat-chat-completions"

    def __init__(self, api_key: str | None, model: str, timeout_seconds: float) -> None:
        self.api_key = api_key
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

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
        headers = {"Authorization": f"Bearer {self.api_key}"}
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
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
            token_usage={k: int(v) for k, v in usage.items() if isinstance(v, int)},
            latency_ms=(time.perf_counter() - start) * 1000,
            finish_reason=finish_reason,
        )
