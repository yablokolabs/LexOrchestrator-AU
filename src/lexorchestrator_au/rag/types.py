from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class SourceDocument:
    source_uri: str
    title: str
    jurisdiction: str = "AU"
    court: str | None = None
    case_type: str | None = None
    doc_type: str | None = None
    citation: str | None = None
    effective_date: str | None = None
    text: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DocumentChunk:
    chunk_index: int
    section: str
    text: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RetrievalFilters:
    jurisdiction: str = "AU"
    court: str | None = None
    case_type: str | None = None
    doc_type: str | None = None


@dataclass(slots=True)
class RetrievalResult:
    chunk_id: str
    document_id: str
    source_uri: str
    title: str
    jurisdiction: str
    court: str | None
    case_type: str | None
    doc_type: str | None
    citation: str | None
    section: str
    text: str
    vector_score: float
    keyword_score: float
    combined_score: float
    metadata: dict[str, Any] = field(default_factory=dict)
