from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    query: str = Field(min_length=3, max_length=8000)
    jurisdiction: str = Field(default="AU", min_length=2, max_length=8)
    court: str | None = Field(default=None, max_length=128)
    case_type: str | None = Field(default=None, max_length=128)
    doc_type: str | None = Field(default=None, max_length=64)
    query_type: str | None = Field(default=None, max_length=64)
    max_citations: int = Field(default=6, ge=1, le=12)
    client_matter_id: str | None = Field(default=None, max_length=128)

    @field_validator("jurisdiction")
    @classmethod
    def normalise_jurisdiction(cls, value: str) -> str:
        return value.upper()


class Citation(BaseModel):
    citation_id: str
    doc_id: str
    chunk_id: str
    title: str
    source_uri: str
    jurisdiction: str
    court: str | None = None
    case_type: str | None = None
    document_citation: str | None = None
    section: str
    snippet: str
    score: float
    trace: dict[str, Any]


class QueryResponse(BaseModel):
    trace_id: str
    answer: str
    citations: list[Citation]
    confidence_score: float = Field(ge=0.0, le=1.0)
    model_used: str
    provider: str
    degraded: bool = False
    latency_ms: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    trace_id: UUID | None = None
    rating: Literal["correct", "incorrect", "partially_correct", "unsafe", "irrelevant"]
    comment: str | None = Field(default=None, max_length=4000)
    corrected_answer: str | None = Field(default=None, max_length=12000)
    user_query: str | None = Field(default=None, max_length=8000)
    model_response: dict[str, Any] | None = None


class FeedbackResponse(BaseModel):
    feedback_id: str
    trace_id: str | None = None
    status: str


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    database: str
    redis: str
    models: dict[str, str]
