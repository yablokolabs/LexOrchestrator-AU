from fastapi import Request

from lexorchestrator_au.api.query_service import QueryService
from lexorchestrator_au.feedback.service import FeedbackService


def get_query_service(request: Request) -> QueryService:
    return request.app.state.query_service  # type: ignore[no-any-return]


def get_feedback_service(request: Request) -> FeedbackService:
    return request.app.state.feedback_service  # type: ignore[no-any-return]
