import asyncio
import logging
import random
from dataclasses import asdict
from typing import Any

from lexorchestrator_au.adapters.base import AdapterError, LLMAdapter, LLMRequest, LLMResponse
from lexorchestrator_au.core.config import Settings
from lexorchestrator_au.core.metrics import LLM_FAILURES, LLM_REQUESTS
from lexorchestrator_au.orchestration.circuit_breaker import CircuitBreaker
from lexorchestrator_au.orchestration.normalizer import normalize_answer
from lexorchestrator_au.orchestration.prompts import SYSTEM_PROMPT, build_user_prompt
from lexorchestrator_au.orchestration.router import ModelRouter

logger = logging.getLogger(__name__)


class LLMOrchestrator:
    def __init__(self, adapters: dict[str, LLMAdapter], router: ModelRouter, settings: Settings) -> None:
        self.adapters = adapters
        self.router = router
        self.settings = settings
        self.breakers = {
            name: CircuitBreaker(
                failure_threshold=settings.circuit_breaker_failure_threshold,
                recovery_seconds=settings.circuit_breaker_recovery_seconds,
            )
            for name in adapters
        }

    async def generate(
        self,
        query: str,
        context_blocks: list[dict[str, Any]],
        jurisdiction: str,
        trace_id: str,
        explicit_query_type: str | None = None,
    ) -> tuple[LLMResponse, dict[str, Any]]:
        route = self.router.route(query, explicit_query_type)
        request = LLMRequest(
            query=query,
            context_blocks=context_blocks,
            jurisdiction=jurisdiction,
            query_type=route.query_type,
            trace_id=trace_id,
            system_prompt=SYSTEM_PROMPT,
            user_prompt=build_user_prompt(query, context_blocks, jurisdiction),
        )

        errors: list[str] = []
        for provider in route.providers:
            adapter = self.adapters.get(provider)
            if not adapter or not adapter.is_available:
                errors.append(f"{provider}:unavailable")
                continue
            breaker = self.breakers[provider]
            if not breaker.allow_request():
                errors.append(f"{provider}:circuit_open")
                continue

            for attempt in range(1, self.settings.llm_retry_attempts + 1):
                try:
                    async with asyncio.timeout(self.settings.llm_timeout_seconds):
                        response = await adapter.generate(request)
                    breaker.record_success()
                    LLM_REQUESTS.labels(provider=provider, status="success").inc()
                    answer, metadata = normalize_answer(response.answer)
                    response.answer = answer
                    metadata.update({"route": asdict(route), "attempt": attempt, "errors": errors})
                    return response, metadata
                except Exception as exc:  # provider SDKs raise provider-specific subclasses
                    breaker.record_failure()
                    LLM_FAILURES.labels(provider=provider).inc()
                    LLM_REQUESTS.labels(provider=provider, status="failure").inc()
                    errors.append(f"{provider}:attempt_{attempt}:{exc.__class__.__name__}")
                    logger.warning(
                        "llm_provider_failed",
                        extra={"trace_id": trace_id, "provider": provider, "attempt": attempt},
                    )
                    if isinstance(exc, AdapterError) and attempt >= self.settings.llm_retry_attempts:
                        break
                    await asyncio.sleep(self._backoff(attempt))

        fallback = self._graceful_fallback(context_blocks, errors)
        metadata = {"route": asdict(route), "errors": errors, "fallback": True}
        return fallback, metadata

    def _backoff(self, attempt: int) -> float:
        base = self.settings.llm_retry_base_delay_seconds
        return min(base * (2 ** (attempt - 1)) + random.uniform(0, base), 3.0)

    def _graceful_fallback(self, context_blocks: list[dict[str, Any]], errors: list[str]) -> LLMResponse:
        if context_blocks:
            answer = (
                "The managed LLM providers were unavailable, so LexOrchestrator-AU returned an extractive, "
                "source-grounded fallback. Review the cited snippets before relying on this output.\n"
            )
            for idx, block in enumerate(context_blocks[:4], start=1):
                answer += f"\n[C{idx}] {block.get('title')} — {block.get('section')}: {str(block.get('text'))[:360]}"
        else:
            answer = (
                "LexOrchestrator-AU could not retrieve relevant Australian legal sources and all model providers "
                "were unavailable. Please retry or narrow the query with a court, statute, or case type."
            )
        return LLMResponse(
            answer=answer,
            provider="fallback",
            model="graceful-degradation",
            raw={"errors": errors},
            degraded=True,
            finish_reason="all_providers_failed",
        )
