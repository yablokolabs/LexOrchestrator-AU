import re
from dataclasses import dataclass

_DRAFTING_RE = re.compile(r"\b(?:draft|clause|letter|submission|pleading)\b", re.I)
_CASE_LAW_RE = re.compile(r"\b(?:case|authority|precedent|court|held|judgment|judgement)\b", re.I)
_STATUTORY_RE = re.compile(r"\b(?:act|section|regulation|statute|schedule)\b", re.I)


@dataclass(frozen=True, slots=True)
class RoutePlan:
    query_type: str
    providers: tuple[str, ...]
    rationale: str


class ModelRouter:
    """Rules-based router. Replace or augment with telemetry-driven policies later."""

    def classify(self, query: str, explicit_type: str | None = None) -> str:
        if explicit_type:
            return explicit_type
        if _DRAFTING_RE.search(query):
            return "drafting"
        if _CASE_LAW_RE.search(query):
            return "case_law"
        if _STATUTORY_RE.search(query):
            return "statutory_interpretation"
        if len(query.split()) > 80:
            return "complex_analysis"
        return "legal_research"

    def route(self, query: str, explicit_type: str | None = None) -> RoutePlan:
        query_type = self.classify(query, explicit_type)
        if query_type in {"case_law", "complex_analysis", "statutory_interpretation"}:
            return RoutePlan(
                query_type=query_type,
                providers=("anthropic", "openai", "llama"),
                rationale="complex legal reasoning benefits from long-context legal synthesis first",
            )
        if query_type == "drafting":
            return RoutePlan(
                query_type=query_type,
                providers=("openai", "anthropic", "llama"),
                rationale="drafting tasks prioritise structured generation and JSON compliance",
            )
        return RoutePlan(
            query_type=query_type,
            providers=("openai", "anthropic", "llama"),
            rationale="routine research uses managed models first; local/extractive Llama is last-only degradation",
        )
