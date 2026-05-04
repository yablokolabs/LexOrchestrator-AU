import time
from collections import OrderedDict, deque
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

_MAX_TRACKED_CLIENTS = 50_000


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    """Per-process sliding-window limiter with LRU eviction to prevent OOM."""

    def __init__(
        self,
        app: ASGIApp,
        limit_per_minute: int,
        burst: int,
        trust_proxy_headers: bool = False,
    ) -> None:
        super().__init__(app)
        self.limit = limit_per_minute
        self.burst = burst
        self.trust_proxy_headers = trust_proxy_headers
        self.window_seconds = 60
        self.requests: OrderedDict[str, deque[float]] = OrderedDict()

    async def dispatch(  # type: ignore[override]
        self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        if request.url.path in {"/health", "/metrics"}:
            resp: Response = await call_next(request)  # type: ignore[misc]
            return resp

        client = self._identify_client(request)
        now = time.monotonic()

        if client not in self.requests:
            if len(self.requests) >= _MAX_TRACKED_CLIENTS:
                self.requests.popitem(last=False)
            self.requests[client] = deque()

        bucket = self.requests[client]
        self.requests.move_to_end(client)

        while bucket and now - bucket[0] > self.window_seconds:
            bucket.popleft()

        allowed = self.limit + self.burst
        if len(bucket) >= allowed:
            retry_after = max(1, int(self.window_seconds - (now - bucket[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests; retry later.",
                    "retry_after_seconds": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        bucket.append(now)
        resp = await call_next(request)  # type: ignore[misc]
        return resp

    def _identify_client(self, request: Request) -> str:
        if self.trust_proxy_headers:
            forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
            if forwarded:
                return forwarded
        return request.client.host if request.client else "unknown"
