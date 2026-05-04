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
        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_legal_chunks_embedding_ivfflat
                ON legal_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)
                WHERE embedding IS NOT NULL
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
