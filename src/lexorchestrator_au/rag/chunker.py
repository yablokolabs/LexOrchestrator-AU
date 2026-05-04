import re
from collections.abc import Iterable

from lexorchestrator_au.rag.types import DocumentChunk, SourceDocument

SECTION_RE = re.compile(
    r"^(?P<label>(?:section|s\.?|part|division|chapter|schedule|clause|rule|article)\s+[\w.()-]+|[A-Z][A-Za-z]+(?:\s+[A-Za-z]+){0,5})\s*$",
    re.I,
)


class LegalChunker:
    """Section-aware chunker for cases, statutes, and practice notes.

    Uses conservative word-token approximation to avoid splitting citations and holdings too
    aggressively. Every chunk carries a stable section label for traceability.
    """

    def __init__(self, target_tokens: int = 420, overlap_tokens: int = 70) -> None:
        if overlap_tokens >= target_tokens:
            raise ValueError("overlap_tokens must be less than target_tokens")
        self.target_tokens = target_tokens
        self.overlap_tokens = overlap_tokens

    def chunk(self, document: SourceDocument) -> list[DocumentChunk]:
        sections = list(self._split_sections(document.text))
        chunks: list[DocumentChunk] = []
        for section_label, section_text in sections:
            words = section_text.split()
            if not words:
                continue
            start = 0
            while start < len(words):
                end = min(len(words), start + self.target_tokens)
                chunk_words = words[start:end]
                chunks.append(
                    DocumentChunk(
                        chunk_index=len(chunks),
                        section=section_label,
                        text=" ".join(chunk_words).strip(),
                        token_count=len(chunk_words),
                        metadata={"source_section": section_label},
                    )
                )
                if end >= len(words):
                    break
                start = max(0, end - self.overlap_tokens)
        return chunks

    @staticmethod
    def _split_sections(text: str) -> Iterable[tuple[str, str]]:
        current_label = "Document"
        buffer: list[str] = []
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                if buffer:
                    buffer.append("")
                continue
            heading = SECTION_RE.match(line)
            if heading and len(line.split()) <= 10:
                if buffer:
                    yield current_label, "\n".join(buffer).strip()
                    buffer = []
                current_label = heading.group("label").strip()
            else:
                buffer.append(line)
        if buffer:
            yield current_label, "\n".join(buffer).strip()
