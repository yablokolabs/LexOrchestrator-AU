import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from lexorchestrator_au.core.config import Settings
from lexorchestrator_au.db import models  # noqa: F401  # ensure metadata registration
from lexorchestrator_au.db.base import Base

logger = logging.getLogger(__name__)


async def initialise_database(engine: AsyncEngine, settings: Settings) -> None:
    """Create extension, tables, and retrieval indexes.

    For beta deployments this keeps setup simple. For regulated production, replace with Alembic
    migrations and run this once from CI/CD.
    """

    if not settings.auto_create_schema:
        return

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
        # HNSW index: works on empty tables (no training required), better recall
        # than IVFFlat for filtered queries, and self-maintaining.
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_legal_chunks_embedding_hnsw
                ON legal_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_legal_chunks_text_fts
                ON legal_chunks USING GIN (to_tsvector('english', text))
                """
            )
        )
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_legal_documents_filters
                ON legal_documents (jurisdiction, court, case_type, doc_type)
                """
            )
        )
    logger.info("database_initialised")
