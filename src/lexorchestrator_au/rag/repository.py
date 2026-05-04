import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lexorchestrator_au.db.models import LegalChunk, LegalDocument
from lexorchestrator_au.rag.types import (
    DocumentChunk,
    RetrievalFilters,
    RetrievalResult,
    SourceDocument,
)

logger = logging.getLogger(__name__)


class DocumentRepository:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        vector_weight: float = 0.70,
        keyword_weight: float = 0.30,
    ) -> None:
        self.session_factory = session_factory
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight

    async def replace_document(
        self,
        document: SourceDocument,
        chunks: Sequence[DocumentChunk],
        embeddings: Sequence[list[float]],
    ) -> uuid.UUID:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have equal length")

        async with self.session_factory() as session:
            existing = await session.scalar(
                select(LegalDocument).where(LegalDocument.source_uri == document.source_uri)
            )
            if existing:
                await session.execute(delete(LegalDocument).where(LegalDocument.id == existing.id))
                await session.flush()

            model = LegalDocument(
                source_uri=document.source_uri,
                title=document.title,
                jurisdiction=document.jurisdiction.upper(),
                court=document.court,
                case_type=document.case_type,
                doc_type=document.doc_type,
                citation=document.citation,
                effective_date=document.effective_date,
                metadata_json=document.metadata,
            )
            session.add(model)
            await session.flush()

            for chunk, embedding in zip(chunks, embeddings, strict=True):
                session.add(
                    LegalChunk(
                        document_id=model.id,
                        chunk_index=chunk.chunk_index,
                        section=chunk.section,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        embedding=embedding,
                        metadata_json=chunk.metadata,
                    )
                )
            await session.commit()
            return model.id

    async def hybrid_search(
        self,
        query: str,
        query_embedding: list[float],
        filters: RetrievalFilters,
        limit: int,
    ) -> list[RetrievalResult]:
        """Hybrid vector + keyword retrieval with jurisdiction/court/case filters."""

        vector_literal = self._vector_literal(query_embedding)
        params: dict[str, Any] = {
            "query": query,
            "embedding": vector_literal,
            "jurisdiction": filters.jurisdiction.upper() if filters.jurisdiction else None,
            "court": filters.court,
            "case_type": filters.case_type,
            "doc_type": filters.doc_type,
            "limit": limit,
            "vector_weight": self.vector_weight,
            "keyword_weight": self.keyword_weight,
        }
        sql = text(
            """
            WITH filtered AS (
              SELECT c.id
              FROM legal_chunks c
              JOIN legal_documents d ON d.id = c.document_id
              WHERE (:jurisdiction IS NULL OR d.jurisdiction = :jurisdiction)
                AND (:court IS NULL OR d.court = :court)
                AND (:case_type IS NULL OR d.case_type = :case_type)
                AND (:doc_type IS NULL OR d.doc_type = :doc_type)
            ),
            vector_candidates AS (
              SELECT c.id
              FROM legal_chunks c
              JOIN filtered f ON f.id = c.id
              WHERE c.embedding IS NOT NULL
              ORDER BY c.embedding <=> CAST(:embedding AS vector)
              LIMIT (:limit * 8)
            ),
            keyword_candidates AS (
              SELECT c.id
              FROM legal_chunks c
              JOIN filtered f ON f.id = c.id
              WHERE to_tsvector('english', c.text) @@ plainto_tsquery('english', :query)
              ORDER BY ts_rank_cd(to_tsvector('english', c.text), plainto_tsquery('english', :query)) DESC
              LIMIT (:limit * 8)
            ),
            candidates AS (
              SELECT id FROM vector_candidates
              UNION
              SELECT id FROM keyword_candidates
            ),
            scored AS (
              SELECT
                c.id::text AS chunk_id,
                d.id::text AS document_id,
                d.source_uri,
                d.title,
                d.jurisdiction,
                d.court,
                d.case_type,
                d.doc_type,
                d.citation,
                c.section,
                c.text,
                c.metadata,
                CASE
                  WHEN c.embedding IS NULL THEN 0
                  ELSE 1 - (c.embedding <=> CAST(:embedding AS vector))
                END AS vector_score,
                ts_rank_cd(to_tsvector('english', c.text), plainto_tsquery('english', :query)) AS keyword_score
              FROM candidates k
              JOIN legal_chunks c ON c.id = k.id
              JOIN legal_documents d ON d.id = c.document_id
            )
            SELECT *, (:vector_weight * vector_score + :keyword_weight * keyword_score) AS combined_score
            FROM scored
            ORDER BY combined_score DESC, keyword_score DESC
            LIMIT :limit
            """
        )
        try:
            async with self.session_factory() as session:
                rows = (await session.execute(sql, params)).mappings().all()
        except Exception:
            logger.exception("hybrid_search_failed")
            raise  # Don't swallow — let the caller handle the error

        return [self._row_to_result(row) for row in rows]

    @staticmethod
    def _row_to_result(row: Any) -> RetrievalResult:
        return RetrievalResult(
            chunk_id=str(row["chunk_id"]),
            document_id=str(row["document_id"]),
            source_uri=row["source_uri"],
            title=row["title"],
            jurisdiction=row["jurisdiction"],
            court=row["court"],
            case_type=row["case_type"],
            doc_type=row["doc_type"],
            citation=row["citation"],
            section=row["section"],
            text=row["text"],
            vector_score=float(row["vector_score"] or 0.0),
            keyword_score=float(row["keyword_score"] or 0.0),
            combined_score=float(row["combined_score"] or 0.0),
            metadata=dict(row["metadata"] or {}),
        )

    @staticmethod
    def _vector_literal(values: Sequence[float]) -> str:
        return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"
