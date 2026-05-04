from lexorchestrator_au.rag.chunker import LegalChunker
from lexorchestrator_au.rag.types import SourceDocument


def test_legal_chunker_preserves_section_labels() -> None:
    doc = SourceDocument(
        source_uri="mock://test",
        title="Test Act",
        text="Section 1\nThis is the first section.\n\nSection 2\nThis is the second section with more words.",
    )
    chunks = LegalChunker(target_tokens=12, overlap_tokens=2).chunk(doc)

    assert chunks
    assert chunks[0].section == "Section 1"
    assert any(chunk.section == "Section 2" for chunk in chunks)
    assert all(chunk.token_count > 0 for chunk in chunks)
