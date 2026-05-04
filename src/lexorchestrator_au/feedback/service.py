import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lexorchestrator_au.core.metrics import FEEDBACK_EVENTS
from lexorchestrator_au.db.models import FeedbackEvent, QueryRun


class FeedbackService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def record_query_run(
        self,
        *,
        trace_id: str,
        user_query: str,
        jurisdiction: str,
        filters: dict[str, Any],
        response: dict[str, Any],
        model_used: str,
        confidence: float,
        latency_ms: float,
        degraded: bool,
    ) -> None:
        try:
            trace_uuid = uuid.UUID(trace_id)
        except ValueError:
            return
        async with self.session_factory() as session:
            session.add(
                QueryRun(
                    trace_id=trace_uuid,
                    user_query=user_query,
                    jurisdiction=jurisdiction,
                    filters=filters,
                    response=response,
                    model_used=model_used,
                    confidence=confidence,
                    latency_ms=latency_ms,
                    degraded=degraded,
                )
            )
            await session.commit()

    async def record_feedback(
        self,
        *,
        trace_id: str | None,
        rating: str,
        comment: str | None,
        corrected_answer: str | None,
        user_query: str | None = None,
        model_response: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        trace_uuid = uuid.UUID(trace_id) if trace_id else None
        async with self.session_factory() as session:
            if trace_uuid:
                query_run = await session.scalar(select(QueryRun).where(QueryRun.trace_id == trace_uuid))
                if query_run:
                    query_run.feedback_rating = rating
                    query_run.feedback_comment = comment
                    query_run.corrected_answer = corrected_answer
                    query_run.feedback_at = datetime.now(UTC)
                    user_query = user_query or query_run.user_query
                    model_response = model_response or query_run.response

            event = FeedbackEvent(
                trace_id=trace_uuid,
                user_query=user_query,
                model_response=model_response or {},
                rating=rating,
                comment=comment,
                corrected_answer=corrected_answer,
            )
            session.add(event)
            await session.commit()
            FEEDBACK_EVENTS.labels(rating=rating).inc()
            return {"feedback_id": str(event.id), "trace_id": trace_id, "status": "recorded"}
