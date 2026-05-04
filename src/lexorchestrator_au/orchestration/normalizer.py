import json
from typing import Any


def normalize_answer(text: str) -> tuple[str, dict[str, Any]]:
    """Normalize provider output into answer text plus optional metadata.

    Providers are asked for JSON, but fallbacks/local models may return plain text. We accept both
    so UI contracts remain stable even during API drift.
    """

    stripped = text.strip()
    if not stripped:
        return "", {"limitations": ["empty_model_response"]}
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped, {"limitations": []}

    if isinstance(payload, dict):
        answer = payload.get("answer")
        if answer is None:
            answer = payload.get("response")
        if answer is None:
            answer = stripped
        metadata = {
            key: value for key, value in payload.items() if key not in {"answer", "response"}
        }
        return str(answer).strip(), metadata
    return stripped, {"limitations": []}
