import asyncio
from pathlib import Path

from lexorchestrator_au.core.cache import create_cache
from lexorchestrator_au.core.config import get_settings
from lexorchestrator_au.db.init_db import initialise_database
from lexorchestrator_au.db.session import create_engine, create_session_factory
from lexorchestrator_au.rag.embeddings import build_embedding_provider
from lexorchestrator_au.rag.ingestion import IngestionPipeline
from lexorchestrator_au.rag.repository import DocumentRepository

PROJECT_ROOT = Path(__file__).resolve().parents[3]


async def run(data_dir: Path | None = None) -> None:
    settings = get_settings()
    engine = create_engine(settings)
    await initialise_database(engine, settings)
    session_factory = create_session_factory(engine)
    cache = await create_cache(settings.redis_url)
    try:
        repository = DocumentRepository(session_factory)
        embeddings = build_embedding_provider(settings, cache=cache)
        pipeline = IngestionPipeline(
            repository=repository,
            embeddings=embeddings,
            batch_size=settings.embedding_batch_size,
        )
        target_dir = data_dir or PROJECT_ROOT / "data" / "mock_legal_docs"
        results = await pipeline.ingest_json_dir(target_dir)
        for _result in results:
            pass
    finally:
        await cache.close()
        await engine.dispose()


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
