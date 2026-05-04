import math
import re
from dataclasses import asdict

from lexorchestrator_au.rag.types import RetrievalResult


def clean_snippet(text: str, max_chars: int = 480) -> str:
    snippet = re.sub(r"\s+", " ", text).strip()
    if len(snippet) <= max_chars:
        return snippet
    return snippet[: max_chars - 1].rstrip() + "…"


class AttributionService:
    def build_citations(
        self, results: list[RetrievalResult], max_citations: int
    ) -> list[dict[str, object]]:
        citations: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for idx, result in enumerate(results, start=1):
            key = (result.document_id, result.section)
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "citation_id": f"C{len(citations) + 1}",
                    "doc_id": result.document_id,
                    "chunk_id": result.chunk_id,
                    "title": result.title,
                    "source_uri": result.source_uri,
                    "jurisdiction": result.jurisdiction,
                    "court": result.court,
                    "case_type": result.case_type,
                    "document_citation": result.citation,
                    "section": result.section,
                    "snippet": clean_snippet(result.text),
                    "score": round(result.combined_score, 4),
                    "trace": {
                        "rank": idx,
                        "vector_score": round(result.vector_score, 4),
                        "keyword_score": round(result.keyword_score, 4),
                    },
                }
            )
            if len(citations) >= max_citations:
                break
        return citations

    def context_blocks(
        self,
        results: list[RetrievalResult],
        max_blocks: int,
        citations: list[dict[str, object]] | None = None,
    ) -> list[dict[str, object]]:
        blocks: list[dict[str, object]] = []
        if citations is not None:
            by_chunk = {result.chunk_id: result for result in results}
            for citation in citations[:max_blocks]:
                result = by_chunk.get(str(citation["chunk_id"]))
                if result is None:
                    continue
                payload = asdict(result)
                payload["citation_id"] = citation["citation_id"]
                blocks.append(payload)
            return blocks

        for citation_id, result in enumerate(results[:max_blocks], start=1):
            payload = asdict(result)
            payload["citation_id"] = f"C{citation_id}"
            blocks.append(payload)
        return blocks

    @staticmethod
    def validate_answer_citations(
        answer: str, citations: list[dict[str, object]]
    ) -> dict[str, object]:
        cited = sorted(set(re.findall(r"\[?(C\d+)\]?", answer)))
        allowed = {str(citation["citation_id"]) for citation in citations}
        unsupported = [citation_id for citation_id in cited if citation_id not in allowed]
        return {
            "cited_source_ids": cited,
            "unsupported_source_ids": unsupported,
            "valid": not unsupported,
        }


class ConfidenceScorer:
    def score(
        self,
        retrieval_results: list[RetrievalResult],
        citations: list[dict[str, object]],
        llm_degraded: bool,
    ) -> float:
        if not retrieval_results or not citations:
            return 0.12 if llm_degraded else 0.2

        top_score = max(result.combined_score for result in retrieval_results)
        score_component = 1 / (1 + math.exp(-top_score))
        citation_component = min(len(citations) / 4, 1.0)
        diversity_component = min(len({citation["doc_id"] for citation in citations}) / 3, 1.0)
        model_component = 0.72 if llm_degraded else 0.9
        confidence = (
            0.45 * score_component
            + 0.25 * citation_component
            + 0.15 * diversity_component
            + 0.15 * model_component
        )
        return round(max(0.0, min(confidence, 0.98)), 3)
