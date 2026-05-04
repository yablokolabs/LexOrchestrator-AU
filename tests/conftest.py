"""Shared test fixtures for LexOrchestrator-AU."""

import pytest

from lexorchestrator_au.core.config import Settings, get_settings
from lexorchestrator_au.rag.types import RetrievalFilters, RetrievalResult, SourceDocument


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    """Ensure each test gets fresh settings."""
    get_settings.cache_clear()
    yield  # type: ignore[misc]
    get_settings.cache_clear()


@pytest.fixture
def test_settings() -> Settings:
    """Settings configured for testing (no external services)."""
    return Settings(
        app_env="test",
        database_url="postgresql+asyncpg://test:test@localhost:5432/test",
        redis_url=None,
        openai_api_key=None,
        anthropic_api_key=None,
        llama_api_url=None,
        embedding_provider="hash",
        lex_api_keys="",
    )


@pytest.fixture
def sample_document() -> SourceDocument:
    return SourceDocument(
        source_uri="mock://test/fair-work",
        title="Fair Work Act 2009 (Cth) — Test Extract",
        jurisdiction="AU",
        court="Fair Work Commission",
        case_type="employment",
        doc_type="statute",
        citation="Fair Work Act 2009 (Cth)",
        text=(
            "Section 385\n"
            "A person has been unfairly dismissed if the Fair Work Commission is satisfied "
            "that the person has been dismissed, the dismissal was harsh, unjust or unreasonable.\n\n"
            "Section 387\n"
            "In considering whether a dismissal was harsh, unjust or unreasonable, the Commission "
            "must take into account whether there was a valid reason related to capacity or conduct."
        ),
    )


@pytest.fixture
def sample_filters() -> RetrievalFilters:
    return RetrievalFilters(jurisdiction="AU", court="Fair Work Commission", case_type="employment")


def make_retrieval_result(
    idx: int = 1,
    *,
    jurisdiction: str = "AU",
    court: str = "High Court of Australia",
    vector_score: float = 0.8,
    keyword_score: float = 0.4,
    combined_score: float = 0.68,
) -> RetrievalResult:
    """Factory for RetrievalResult test instances."""
    return RetrievalResult(
        chunk_id=f"chunk-{idx}",
        document_id=f"doc-{idx}",
        source_uri=f"mock://doc-{idx}",
        title=f"Document {idx}",
        jurisdiction=jurisdiction,
        court=court,
        case_type="administrative",
        doc_type="case",
        citation=f"Example [{2024 + idx}] HCA {idx}",
        section="Principle",
        text="Procedural fairness requires disclosure of credible relevant adverse material.",
        vector_score=vector_score,
        keyword_score=keyword_score,
        combined_score=combined_score,
    )
