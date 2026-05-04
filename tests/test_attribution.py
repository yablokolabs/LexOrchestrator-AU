from conftest import make_retrieval_result

from lexorchestrator_au.attribution.service import AttributionService, ConfidenceScorer


class TestAttributionService:
    def test_citations_are_traceable_and_deduped(self) -> None:
        results = [make_retrieval_result(1), make_retrieval_result(2)]
        citations = AttributionService().build_citations(results, max_citations=2)

        assert len(citations) == 2
        assert citations[0]["doc_id"] == "doc-1"
        assert citations[0]["chunk_id"] == "chunk-1"
        assert citations[0]["trace"]["rank"] == 1
        assert citations[1]["citation_id"] == "C2"

    def test_citations_dedup_same_doc_section(self) -> None:
        r1 = make_retrieval_result(1)
        r2 = make_retrieval_result(2)
        # Force same doc_id + section → should dedup
        r2.document_id = r1.document_id
        r2.section = r1.section
        citations = AttributionService().build_citations([r1, r2], max_citations=5)
        assert len(citations) == 1

    def test_max_citations_limits_output(self) -> None:
        results = [make_retrieval_result(i) for i in range(5)]
        citations = AttributionService().build_citations(results, max_citations=1)
        assert len(citations) == 1

    def test_empty_results(self) -> None:
        citations = AttributionService().build_citations([], max_citations=5)
        assert citations == []

    def test_validate_answer_citations_detects_unsupported(self) -> None:
        citations = [{"citation_id": "C1"}, {"citation_id": "C2"}]
        result = AttributionService.validate_answer_citations("See [C1] and [C3].", citations)
        assert result["unsupported_source_ids"] == ["C3"]
        assert "C1" in result["cited_source_ids"]

    def test_context_blocks_from_citations(self) -> None:
        results = [make_retrieval_result(1), make_retrieval_result(2)]
        service = AttributionService()
        citations = service.build_citations(results, max_citations=2)
        blocks = service.context_blocks(results, max_blocks=10, citations=citations)
        assert len(blocks) == 2
        assert blocks[0]["citation_id"] == "C1"


class TestConfidenceScorer:
    def test_confidence_is_bounded(self) -> None:
        results = [make_retrieval_result(1)]
        citations = AttributionService().build_citations(results, max_citations=1)
        score = ConfidenceScorer().score(results, citations, llm_degraded=False)
        assert 0.0 <= score <= 0.98

    def test_degraded_model_lowers_confidence(self) -> None:
        results = [make_retrieval_result(1)]
        citations = AttributionService().build_citations(results, max_citations=1)
        normal = ConfidenceScorer().score(results, citations, llm_degraded=False)
        degraded = ConfidenceScorer().score(results, citations, llm_degraded=True)
        assert degraded < normal

    def test_empty_results_gives_low_confidence(self) -> None:
        score = ConfidenceScorer().score([], [], llm_degraded=False)
        assert score == 0.2

    def test_empty_degraded_gives_lowest_confidence(self) -> None:
        score = ConfidenceScorer().score([], [], llm_degraded=True)
        assert score == 0.12
