import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import text

from lexorchestrator_au.api.dependencies import get_feedback_service, get_query_service
from lexorchestrator_au.api.query_service import QueryService
from lexorchestrator_au.api.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
)
from lexorchestrator_au.core.metrics import metrics_bytes
from lexorchestrator_au.feedback.service import FeedbackService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1")
legacy_router = APIRouter()

QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


async def _health(request: Request) -> HealthResponse:
    database = "unknown"
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "degraded"

    cache = getattr(request.app.state, "cache", None)
    if cache is not None:
        redis_healthy = await cache.is_healthy()
        redis_state = "ok" if redis_healthy else "degraded"
    else:
        redis_state = "not_configured"

    adapters = getattr(request.app.state, "adapters", {})
    model_states = {
        name: ("available" if adapter.is_available else "not_configured")
        for name, adapter in adapters.items()
    }
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        app="LexOrchestrator-AU",
        database=database,
        redis=redis_state,
        models=model_states,
    )


async def _query(
    payload: QueryRequest, request: Request, service: QueryServiceDep
) -> QueryResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return await service.query(payload, trace_id=trace_id)


async def _feedback(payload: FeedbackRequest, service: FeedbackServiceDep) -> FeedbackResponse:
    try:
        result = await service.record_feedback(**payload.model_dump())
        return FeedbackResponse(**result)
    except Exception:
        logger.exception("feedback_persistence_failed")
        return FeedbackResponse(
            feedback_id=f"not-persisted-{uuid.uuid4()}",
            trace_id=str(payload.trace_id) if payload.trace_id else None,
            status="degraded_not_stored",
        )


async def _metrics() -> Response:
    return Response(content=metrics_bytes(), media_type="text/plain; version=0.0.4")


# Register versioned routes
router.get("/health", response_model=HealthResponse)(_health)
router.post("/query", response_model=QueryResponse)(_query)
router.post("/feedback", response_model=FeedbackResponse)(_feedback)
router.get("/metrics")(_metrics)

# Legacy unversioned routes (backward compatibility)
legacy_router.get("/health", response_model=HealthResponse, include_in_schema=False)(_health)
legacy_router.post("/query", response_model=QueryResponse, include_in_schema=False)(_query)
legacy_router.post("/feedback", response_model=FeedbackResponse, include_in_schema=False)(_feedback)
legacy_router.get("/metrics", include_in_schema=False)(_metrics)
