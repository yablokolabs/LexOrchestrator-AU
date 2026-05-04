import re
import time
from typing import Any

import httpx

from lexorchestrator_au.adapters.base import APIDriftError, LLMRequest, LLMResponse


class LlamaAdapterV1:
    """Local/API Llama adapter with a deterministic extractive fallback.

    If LLAMA_API_URL is set, the adapter calls a local vLLM/Ollama-compatible HTTP service.
    Without a URL, it still returns grounded extractive output so the SaaS can degrade gracefully.
    """

    name = "llama"
    version = "local-json-or-extractive-v1"

    def __init__(self, api_url: str | None, model: str, timeout_seconds: float) -> None:
        self.api_url = api_url.rstrip("/") if api_url else None
        self.model = model
        self.timeout_seconds = timeout_seconds

    @property
    def is_available(self) -> bool:
        return True

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_url:
            return self._extractive_response(request)

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
            "temperature": 0.1,
        }
        start = time.perf_counter()
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(f"{self.api_url}/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()

        answer = self._parse_common_chat_response(data)
        return LLMResponse(
            answer=answer,
            provider=self.name,
            model=self.model,
            raw={"adapter_version": self.version},
            latency_ms=(time.perf_counter() - start) * 1000,
        )

    def _extractive_response(self, request: LLMRequest) -> LLMResponse:
        start = time.perf_counter()
        if not request.context_blocks:
            answer = (
                "I could not locate sufficiently relevant Australian legal source material for this query. "
                "Please provide more facts, a court, or a statute/case reference so the system can retrieve grounded authorities."
            )
        else:
            bullets = []
            for idx, block in enumerate(request.context_blocks[:4], start=1):
                snippet = re.sub(r"\s+", " ", str(block.get("text", ""))).strip()
                snippet = snippet[:420].rstrip()
                section = block.get("section") or "source section"
                title = block.get("title") or block.get("document_id")
                bullets.append(f"[C{idx}] {title}, {section}: {snippet}")
            answer = (
                "Grounded summary based on retrieved Australian legal materials:\n"
                + "\n".join(f"- {bullet}" for bullet in bullets)
                + "\n\nThis is an evidence-grounded research response, not a substitute for solicitor review."
            )
        return LLMResponse(
            answer=answer,
            provider=self.name,
            model=f"{self.model}:extractive-fallback",
            raw={"adapter_version": self.version, "mode": "extractive"},
            latency_ms=(time.perf_counter() - start) * 1000,
            degraded=not bool(self.api_url),
            finish_reason="extractive_fallback",
        )

    @staticmethod
    def _parse_common_chat_response(data: dict[str, Any]) -> str:
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except (KeyError, IndexError, TypeError) as exc:
            # Ollama generate/chat compatibility.
            answer = data.get("message", {}).get("content") or data.get("response")
            if isinstance(answer, str) and answer.strip():
                return answer.strip()
            raise APIDriftError(f"Unexpected Llama-compatible response: {data!r}") from exc
