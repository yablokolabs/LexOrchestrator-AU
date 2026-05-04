from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Simple API-key gate for beta SaaS deployments.

    Set LEX_API_KEYS to a comma-separated key list. If unset, auth is disabled for local dev.
    """

    def __init__(self, app, api_keys: list[str]) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.api_keys = {key for key in api_keys if key}
        self.public_paths = {"/health", "/docs", "/openapi.json"}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if not self.api_keys or request.url.path in self.public_paths:
            return await call_next(request)

        supplied = request.headers.get("x-api-key")
        if supplied not in self.api_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "trace_id": getattr(request.state, "trace_id", None),
                    "message": "Missing or invalid API key.",
                },
            )
        return await call_next(request)
