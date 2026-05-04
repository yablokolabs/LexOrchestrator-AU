import asyncio
import time
from dataclasses import dataclass, field
from enum import StrEnum


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(slots=True)
class CircuitBreaker:
    failure_threshold: int
    recovery_seconds: float
    failures: int = 0
    opened_at: float | None = None
    state: CircuitState = CircuitState.CLOSED
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)
    _half_open_in_flight: bool = field(default=False, repr=False)

    async def allow_request(self) -> bool:
        async with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if (
                self.state == CircuitState.OPEN
                and self.opened_at is not None
                and time.monotonic() - self.opened_at >= self.recovery_seconds
            ):
                self.state = CircuitState.HALF_OPEN
                self._half_open_in_flight = True
                return True
            if self.state == CircuitState.HALF_OPEN and not self._half_open_in_flight:
                # Only one probe request allowed in HALF_OPEN
                self._half_open_in_flight = True
                return True
            return self.state == CircuitState.HALF_OPEN and False

    async def record_success(self) -> None:
        async with self._lock:
            self.failures = 0
            self.opened_at = None
            self.state = CircuitState.CLOSED
            self._half_open_in_flight = False

    async def record_failure(self) -> None:
        async with self._lock:
            self.failures += 1
            self._half_open_in_flight = False
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.opened_at = time.monotonic()
