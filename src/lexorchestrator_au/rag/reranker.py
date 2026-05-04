import re
from collections.abc import Sequence

from lexorchestrator_au.rag.types import RetrievalFilters, RetrievalResult


class SimpleLegalReranker:
    """Lightweight reranker that rewards exact legal terms and filter alignment."""

    def rerank(
        self,
        query: str,
        results: Sequence[RetrievalResult],
        filters: RetrievalFilters,
        limit: int,
    ) -> list[RetrievalResult]:
        terms = {term for term in re.findall(r"[a-zA-Z][a-zA-Z0-9'-]{2,}", query.lower())}

        def score(result: RetrievalResult) -> float:
            text = f"{result.title} {result.section} {result.text}".lower()
            exact_hits = sum(1 for term in terms if term in text)
            filter_bonus = 0.0
            if filters.court and result.court == filters.court:
                filter_bonus += 0.08
            if filters.case_type and result.case_type == filters.case_type:
                filter_bonus += 0.08
            if filters.jurisdiction and result.jurisdiction.upper() == filters.jurisdiction.upper():
                filter_bonus += 0.04
            return result.combined_score + min(exact_hits * 0.015, 0.15) + filter_bonus

        return sorted(results, key=score, reverse=True)[:limit]
