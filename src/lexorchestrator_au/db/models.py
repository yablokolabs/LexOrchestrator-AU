import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lexorchestrator_au.db.base import Base

# Default dimension; overridden at runtime via Settings.embedding_dimensions.
# The actual Vector column size is set here for initial schema creation.
# For production, use Alembic migrations to alter the column if dimensions change.
DEFAULT_EMBEDDING_DIMENSIONS = 384


def utcnow() -> datetime:
    return datetime.now(UTC)


class LegalDocument(Base):
    __tablename__ = "legal_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(16), nullable=False, index=True, default="AU")
    court: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    case_type: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    doc_type: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    citation: Mapped[str | None] = mapped_column(String(256), nullable=True)
    effective_date: Mapped[datetime | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    chunks: Mapped[list["LegalChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (UniqueConstraint("source_uri", name="uq_legal_documents_source_uri"),)


class LegalChunk(Base):
    __tablename__ = "legal_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("legal_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(nullable=False)
    section: Mapped[str] = mapped_column(String(256), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(DEFAULT_EMBEDDING_DIMENSIONS), nullable=True
    )
    metadata_json: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    document: Mapped[LegalDocument] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_legal_chunks_document_index"),
        Index("ix_legal_chunks_section", "section"),
    )


class QueryRun(Base):
    __tablename__ = "query_runs"

    trace_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    user_query: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(16), nullable=False, default="AU")
    filters: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    model_used: Mapped[str] = mapped_column(String(256), nullable=False)
    confidence: Mapped[float] = mapped_column(nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(nullable=False, default=0.0)
    degraded: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
    feedback_rating: Mapped[str | None] = mapped_column(String(32), nullable=True)
    feedback_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class FeedbackEvent(Base):
    __tablename__ = "feedback_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )
    user_query: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_response: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    rating: Mapped[str] = mapped_column(String(32), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, index=True
    )
