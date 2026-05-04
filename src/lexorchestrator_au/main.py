import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from lexorchestrator_au.adapters.registry import build_adapters
from lexorchestrator_au.api.query_service import QueryService
from lexorchestrator_au.api.routes import router
from lexorchestrator_au.attribution.service import AttributionService, ConfidenceScorer
from lexorchestrator_au.core.cache import create_cache
from lexorchestrator_au.core.config import get_settings
from lexorchestrator_au.core.logging import configure_logging
from lexorchestrator_au.core.middleware import RequestContextMiddleware
from lexorchestrator_au.core.rate_limit import InMemoryRateLimitMiddleware
from lexorchestrator_au.db.init_db import initialise_database
from lexorchestrator_au.db.session import create_engine, create_session_factory
from lexorchestrator_au.feedback.service import FeedbackService
from lexorchestrator_au.orchestration.orchestrator import LLMOrchestrator
from lexorchestrator_au.orchestration.router import ModelRouter
from lexorchestrator_au.rag.embeddings import build_embedding_provider
from lexorchestrator_au.rag.repository import DocumentRepository
from lexorchestrator_au.rag.retrieval import RetrievalService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)

    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    try:
        await initialise_database(engine, settings)
    except Exception:
        logger.exception("database_initialisation_failed_app_will_degrade")

    cache = await create_cache(settings.redis_url)
    app.state.cache = cache

    adapters = build_adapters(settings)
    app.state.adapters = adapters

    repository = DocumentRepository(session_factory)
    embeddings = build_embedding_provider(settings, cache=cache)
    retrieval = RetrievalService(repository, embeddings)
    feedback_service = FeedbackService(session_factory)
    orchestrator = LLMOrchestrator(adapters, ModelRouter(), settings)
    query_service = QueryService(
        retrieval=retrieval,
        orchestrator=orchestrator,
        attribution=AttributionService(),
        confidence=ConfidenceScorer(),
        feedback=feedback_service,
        settings=settings,
    )
    app.state.feedback_service = feedback_service
    app.state.query_service = query_service

    yield

    await cache.close()
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="LexOrchestrator-AU",
        version="0.1.0",
        description="Jurisdiction-aware LLM orchestration and legal RAG backend for Australian law firms.",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        limit_per_minute=settings.rate_limit_per_minute,
        burst=settings.rate_limit_burst,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "trace_id": trace_id, "details": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        trace_id = getattr(request.state, "trace_id", None)
        logger.exception("unhandled_request_error", extra={"trace_id": trace_id})
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "trace_id": trace_id,
                "message": "LexOrchestrator-AU could not complete the request safely.",
            },
        )

    return app


app = create_app()
