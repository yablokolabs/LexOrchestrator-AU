import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process token-window limiter; Redis can be introduced behind the same contract."""

    def __init__(self, app, limit_per_minute: int, burst: int, trust_proxy_headers: bool = False) -> None:  # type: ignore[no-untyped-def]
        super().__init__(app)
        self.limit = limit_per_minute
        self.burst = burst
        self.trust_proxy_headers = trust_proxy_headers
        self.window_seconds = 60
        self.requests: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Response]) -> Response:
        if request.url.path in {"/health", "/metrics"}:
            return await call_next(request)

        if self.trust_proxy_headers:
            client = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        else:
            client = ""
        if not client:
            client = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = self.requests[client]
        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()
        allowed = self.limit + self.burst
        if len(bucket) >= allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests; retry later.",
                    "retry_after_seconds": max(1, int(self.window_seconds - (now - bucket[0]))),
                },
            )
        bucket.append(now)
        return await call_next(request)
