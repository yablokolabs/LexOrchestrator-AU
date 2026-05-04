import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        incoming_trace_id = request.headers.get("x-trace-id")
        try:
            trace_id = str(uuid.UUID(incoming_trace_id)) if incoming_trace_id else str(uuid.uuid4())
        except (TypeError, ValueError):
            trace_id = str(uuid.uuid4())
        request.state.trace_id = trace_id
        start = time.perf_counter()
        response: Response = await call_next(request)  # type: ignore[misc]
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["x-trace-id"] = trace_id
        logger.info(
            "request_completed",
            extra={"trace_id": trace_id, "path": request.url.path, "duration_ms": duration_ms},
        )
        return response
