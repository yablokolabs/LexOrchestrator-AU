import hmac
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

_MIN_API_KEY_LENGTH = 16


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """API-key gate for beta SaaS deployments.

    Uses constant-time comparison to prevent timing attacks.
    Set LEX_API_KEYS to a comma-separated key list. If unset, auth is disabled for local dev.
    """

    def __init__(self, app, api_keys: list[str]) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.api_keys = [key for key in api_keys if key and len(key) >= _MIN_API_KEY_LENGTH]
        self.public_paths = {"/health", "/docs", "/openapi.json", "/metrics"}

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if not self.api_keys or request.url.path in self.public_paths:
            response: Response = await call_next(request)  # type: ignore[misc]
            return response

        supplied = request.headers.get("x-api-key", "")
        if not self._is_valid_key(supplied):
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "trace_id": getattr(request.state, "trace_id", None),
                    "message": "Missing or invalid API key.",
                },
            )
        resp: Response = await call_next(request)  # type: ignore[misc]
        return resp

    def _is_valid_key(self, supplied: str) -> bool:
        """Constant-time comparison against all configured keys."""
        if not supplied:
            return False
        return any(hmac.compare_digest(supplied.encode(), key.encode()) for key in self.api_keys)
