from lexorchestrator_au.attribution.service import AttributionService, ConfidenceScorer
from lexorchestrator_au.rag.types import RetrievalResult


def result(idx: int) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=f"chunk-{idx}",
        document_id=f"doc-{idx}",
        source_uri=f"mock://doc-{idx}",
        title=f"Document {idx}",
        jurisdiction="AU",
        court="High Court of Australia",
        case_type="administrative",
        doc_type="case",
        citation="Example [2024] HCA 1",
        section="Principle",
        text="Procedural fairness requires disclosure of credible relevant adverse material.",
        vector_score=0.8,
        keyword_score=0.4,
        combined_score=0.68,
    )


def test_citations_are_traceable_and_confidence_is_bounded() -> None:
    results = [result(1), result(2)]
    citations = AttributionService().build_citations(results, max_citations=2)
    confidence = ConfidenceScorer().score(results, citations, llm_degraded=False)

    assert citations[0]["doc_id"] == "doc-1"
    assert citations[0]["chunk_id"] == "chunk-1"
    assert citations[0]["trace"]["rank"] == 1
    assert 0.0 <= confidence <= 1.0
