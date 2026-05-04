from dataclasses import dataclass, field
from typing import Any, Protocol


class AdapterError(Exception):
    """Base class for adapter failures."""


class ProviderUnavailable(AdapterError):
    """Provider is not configured or cannot be reached."""


class APIDriftError(AdapterError):
    """Provider response shape changed enough that parsing is unsafe."""


@dataclass(slots=True)
class LLMRequest:
    query: str
    context_blocks: list[dict[str, Any]]
    jurisdiction: str
    query_type: str
    trace_id: str
    system_prompt: str
    user_prompt: str


@dataclass(slots=True)
class LLMResponse:
    answer: str
    provider: str
    model: str
    raw: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    degraded: bool = False
    finish_reason: str | None = None


class LLMAdapter(Protocol):
    name: str
    version: str
    model: str

    @property
    def is_available(self) -> bool:
        ...

    async def generate(self, request: LLMRequest) -> LLMResponse:
        ...
