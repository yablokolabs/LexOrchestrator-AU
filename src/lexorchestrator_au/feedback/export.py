import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lexorchestrator_au.db.models import FeedbackEvent, QueryRun


class FineTuningDatasetExporter:
    """Export reviewed feedback into JSONL for future eval/fine-tuning pipelines."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self.session_factory = session_factory

    async def export_jsonl(self, output_path: Path) -> dict[str, Any]:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        async with self.session_factory() as session:
            rows = (
                await session.execute(
                    select(QueryRun, FeedbackEvent)
                    .join(FeedbackEvent, FeedbackEvent.trace_id == QueryRun.trace_id)
                    .where(FeedbackEvent.corrected_answer.is_not(None))
                    .order_by(FeedbackEvent.created_at.asc())
                )
            ).all()

        with output_path.open("w", encoding="utf-8") as handle:
            for query_run, feedback in rows:
                record = {
                    "trace_id": str(query_run.trace_id),
                    "jurisdiction": query_run.jurisdiction,
                    "input": query_run.user_query,
                    "accepted_answer": feedback.corrected_answer,
                    "original_response": query_run.response,
                    "feedback_rating": feedback.rating,
                    "feedback_comment": feedback.comment,
                    "created_at": feedback.created_at.isoformat(),
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                count += 1
        return {"output_path": str(output_path), "records": count}
