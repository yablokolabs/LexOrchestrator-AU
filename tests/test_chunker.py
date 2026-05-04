import pytest

from lexorchestrator_au.rag.chunker import LegalChunker
from lexorchestrator_au.rag.types import SourceDocument


class TestLegalChunker:
    def test_preserves_section_labels(self, sample_document: SourceDocument) -> None:
        chunks = LegalChunker(target_tokens=12, overlap_tokens=2).chunk(sample_document)

        assert chunks
        assert chunks[0].section == "Section 385"
        assert any(chunk.section == "Section 387" for chunk in chunks)
        assert all(chunk.token_count > 0 for chunk in chunks)

    def test_empty_document(self) -> None:
        doc = SourceDocument(source_uri="mock://empty", title="Empty", text="")
        chunks = LegalChunker().chunk(doc)
        assert chunks == []

    def test_whitespace_only_document(self) -> None:
        doc = SourceDocument(source_uri="mock://ws", title="Whitespace", text="   \n\n  \n  ")
        chunks = LegalChunker().chunk(doc)
        assert chunks == []

    def test_single_section_no_heading(self) -> None:
        doc = SourceDocument(
            source_uri="mock://noheading",
            title="No heading",
            text="This is a paragraph without any section heading at all.",
        )
        chunks = LegalChunker(target_tokens=5, overlap_tokens=1).chunk(doc)
        assert chunks
        assert all(chunk.section == "Document" for chunk in chunks)

    def test_overlap_must_be_less_than_target(self) -> None:
        with pytest.raises(ValueError, match="overlap_tokens must be less than target_tokens"):
            LegalChunker(target_tokens=10, overlap_tokens=10)

    def test_overlap_creates_redundant_content(self) -> None:
        doc = SourceDocument(
            source_uri="mock://overlap",
            title="Overlap Test",
            text="word1 word2 word3 word4 word5 word6 word7 word8 word9 word10",
        )
        chunks = LegalChunker(target_tokens=5, overlap_tokens=2).chunk(doc)
        assert len(chunks) >= 2
        # Overlap means the end of chunk N appears at the start of chunk N+1
        last_words_first = chunks[0].text.split()[-2:]
        first_words_second = chunks[1].text.split()[:2]
        assert last_words_first == first_words_second

    def test_chunk_index_is_sequential(self) -> None:
        doc = SourceDocument(
            source_uri="mock://idx",
            title="Index Test",
            text="Section 1\n" + " ".join(f"word{i}" for i in range(100)),
        )
        chunks = LegalChunker(target_tokens=20, overlap_tokens=3).chunk(doc)
        for i, chunk in enumerate(chunks):
            assert chunk.chunk_index == i
