import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from nooa_governance import (
    BudgetExceededError,
    GovernedMixin,
    RetryCircuitOpenError,
    TimeBudgetExceededError,
)


class _Agent(GovernedMixin):
    pass


def _make_agent(**kwargs) -> _Agent:
    agent = _Agent()
    agent.init_governance(**kwargs)
    return agent


def test_successful_call_consumes_one_call_budget():
    async def run():
        agent = _make_agent(max_calls=3, max_retries_per_call=1, timeout_s=1.0)

        async def ok():
            return "result"

        result = await agent.governed_call("ok", ok)

        assert result == "result"
        report = agent.governance_report()
        assert report["calls_made"] == 1
        assert report["calls_remaining"] == 2
        assert report["retries_used"] == 0
        assert report["failures"] == 0

    asyncio.run(run())


def test_budget_exceeded_raises_without_calling_coro_again():
    async def run():
        agent = _make_agent(max_calls=1, max_retries_per_call=0, timeout_s=1.0)
        calls = []

        async def ok():
            calls.append(1)
            return "result"

        await agent.governed_call("ok", ok)
        with pytest.raises(BudgetExceededError):
            await agent.governed_call("ok", ok)

        assert calls == [1]  # the second, over-budget call never executed

    asyncio.run(run())


def test_retries_then_succeeds():
    async def run():
        agent = _make_agent(max_calls=5, max_retries_per_call=2, timeout_s=1.0)
        attempts = {"n": 0}

        async def flaky():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise ValueError("transient")
            return "ok"

        with patch("nooa_governance.asyncio.sleep", new=AsyncMock(return_value=None)):
            result = await agent.governed_call("flaky", flaky)

        assert result == "ok"
        report = agent.governance_report()
        assert report["retries_used"] == 2
        assert report["failures"] == 2
        assert report["calls_made"] == 1  # one governed_call, regardless of retries

    asyncio.run(run())


def test_retry_circuit_opens_after_max_retries():
    async def run():
        agent = _make_agent(max_calls=5, max_retries_per_call=1, timeout_s=1.0)

        async def always_fails():
            raise ValueError("nope")

        with patch("nooa_governance.asyncio.sleep", new=AsyncMock(return_value=None)):
            with pytest.raises(RetryCircuitOpenError):
                await agent.governed_call("always_fails", always_fails)

        report = agent.governance_report()
        assert report["failures"] == 2  # first try + 1 retry
        assert report["calls_made"] == 1  # still one call against the budget

    asyncio.run(run())


def test_non_retryable_exception_is_not_retried():
    async def run():
        agent = _make_agent(
            max_calls=5, max_retries_per_call=3, timeout_s=1.0, non_retryable=(PermissionError,)
        )
        attempts = {"n": 0}

        async def bad_auth():
            attempts["n"] += 1
            raise PermissionError("invalid api key")

        with pytest.raises(PermissionError):
            await agent.governed_call("bad_auth", bad_auth)

        assert attempts["n"] == 1  # no retries attempted
        report = agent.governance_report()
        assert report["retries_used"] == 0
        assert report["failures"] == 1

    asyncio.run(run())


def test_timeout_per_attempt_opens_circuit():
    async def run():
        # max_retries_per_call=0 keeps this fast: no backoff sleep to mock out.
        agent = _make_agent(max_calls=5, max_retries_per_call=0, timeout_s=0.05)

        async def hangs():
            await asyncio.sleep(10)

        with pytest.raises(RetryCircuitOpenError):
            await agent.governed_call("hangs", hangs)

    asyncio.run(run())


def test_max_total_time_s_exhausted():
    async def run():
        agent = _make_agent(max_calls=5, max_retries_per_call=0, timeout_s=1.0, max_total_time_s=0.0)

        async def ok():
            return "result"

        with pytest.raises(TimeBudgetExceededError):
            await agent.governed_call("ok", ok)

    asyncio.run(run())


def test_governance_report_exposes_configured_limits():
    async def run():
        agent = _make_agent(max_calls=7, max_retries_per_call=2, timeout_s=12.5, max_total_time_s=100.0)
        report = agent.governance_report()

        assert report["max_calls"] == 7
        assert report["max_retries_per_call"] == 2
        assert report["timeout_s"] == 12.5
        assert report["max_total_time_s"] == 100.0

    asyncio.run(run())
