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

router = APIRouter()
QueryServiceDep = Annotated[QueryService, Depends(get_query_service)]
FeedbackServiceDep = Annotated[FeedbackService, Depends(get_feedback_service)]


@router.get("/health", response_model=HealthResponse)
async def health(request: Request) -> HealthResponse:
    database = "unknown"
    try:
        async with request.app.state.session_factory() as session:
            await session.execute(text("SELECT 1"))
        database = "ok"
    except Exception:
        database = "degraded"

    cache = getattr(request.app.state, "cache", None)
    redis_state = cache.__class__.__name__ if cache else "not_configured"
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


@router.post("/query", response_model=QueryResponse)
async def query(
    payload: QueryRequest,
    request: Request,
    service: QueryServiceDep,
) -> QueryResponse:
    trace_id = getattr(request.state, "trace_id", None)
    return await service.query(payload, trace_id=trace_id)


@router.post("/feedback", response_model=FeedbackResponse)
async def feedback(
    payload: FeedbackRequest,
    service: FeedbackServiceDep,
) -> FeedbackResponse:
    try:
        result = await service.record_feedback(**payload.model_dump())
        return FeedbackResponse(**result)
    except Exception:
        logger.exception("feedback_persistence_failed")
        return FeedbackResponse(
            feedback_id=f"not-persisted-{uuid.uuid4()}",
            trace_id=payload.trace_id,
            status="degraded_not_stored",
        )


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=metrics_bytes(), media_type="text/plain; version=0.0.4")
