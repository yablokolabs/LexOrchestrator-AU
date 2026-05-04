from lexorchestrator_au.adapters.anthropic import AnthropicMessagesAdapterV1
from lexorchestrator_au.adapters.base import LLMAdapter
from lexorchestrator_au.adapters.llama import LlamaAdapterV1
from lexorchestrator_au.adapters.openai import OpenAIChatAdapterV1
from lexorchestrator_au.core.config import Settings


def build_adapters(settings: Settings) -> dict[str, LLMAdapter]:
    adapters: list[LLMAdapter] = [
        AnthropicMessagesAdapterV1(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
        OpenAIChatAdapterV1(
            api_key=settings.openai_api_key,
            model=settings.openai_model,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
        LlamaAdapterV1(
            api_url=settings.llama_api_url,
            model=settings.llama_model,
            timeout_seconds=settings.llm_timeout_seconds,
        ),
    ]
    return {adapter.name: adapter for adapter in adapters}
