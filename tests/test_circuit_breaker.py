import asyncio

import pytest

from lexorchestrator_au.orchestration.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    @pytest.fixture
    def breaker(self) -> CircuitBreaker:
        return CircuitBreaker(failure_threshold=3, recovery_seconds=0.1)

    async def test_starts_closed(self, breaker: CircuitBreaker) -> None:
        assert breaker.state == CircuitState.CLOSED
        assert await breaker.allow_request()

    async def test_opens_after_threshold_failures(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN
        assert not await breaker.allow_request()

    async def test_half_open_after_recovery(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

        await asyncio.sleep(0.15)
        assert await breaker.allow_request()
        assert breaker.state == CircuitState.HALF_OPEN

    async def test_success_in_half_open_closes(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            await breaker.record_failure()
        await asyncio.sleep(0.15)
        await breaker.allow_request()  # transition to HALF_OPEN
        await breaker.record_success()
        assert breaker.state == CircuitState.CLOSED

    async def test_failure_in_half_open_reopens(self, breaker: CircuitBreaker) -> None:
        for _ in range(3):
            await breaker.record_failure()
        await asyncio.sleep(0.15)
        await breaker.allow_request()
        await breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    async def test_single_probe_in_half_open(self, breaker: CircuitBreaker) -> None:
        """Only one request should be allowed through in HALF_OPEN."""
        for _ in range(3):
            await breaker.record_failure()
        await asyncio.sleep(0.15)

        first = await breaker.allow_request()
        second = await breaker.allow_request()
        assert first is True
        assert second is False
