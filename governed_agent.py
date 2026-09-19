"""
GovernedAgent: object-oriented cost/retry/timeout governance for NOOA agents.

The problem this addresses is real and documented: a June 2026 preprint catalogued
63 LLM-agent budget-overrun incidents across 21 orchestration frameworks, with
uncontrolled retry loops as a leading cause (see README for sources). Every existing
fix -- agent-gov, LiteLLM per-key budgets, Microsoft's Agent Governance Toolkit --
works as a reverse proxy sitting between the agent and the LLM provider: external,
opaque to the agent's own codebase, and untestable alongside the agent's own logic.

NOOA agents are plain Python classes. That makes a different answer possible:
governance as an ordinary, inheritable, unit-testable base class, living in the same
codebase as the agent it governs, instead of a network gateway nobody can see.

Budget/retry state lives in plain Python fields. Enforcement lives in plain,
deterministic Python methods -- never the `...`-body LLM-completed kind -- so
governance holds regardless of what the model decides to do.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class BudgetExceededError(RuntimeError):
    """Raised when a governed call would exceed the agent's remaining call budget."""


class RetryCircuitOpenError(RuntimeError):
    """Raised when the retry circuit breaker trips after repeated failures on one call."""


@dataclass
class GovernanceLedger:
    """Deterministic, auditable record of every governed call an agent made."""

    max_calls: int
    max_retries_per_call: int
    calls_made: int = 0
    retries_used: int = 0
    failures: int = 0
    log: list[dict[str, Any]] = field(default_factory=list)

    def remaining_calls(self) -> int:
        return self.max_calls - self.calls_made

    def record(self, method: str, attempt: int, outcome: str, elapsed_s: float) -> None:
        self.log.append(
            {
                "method": method,
                "attempt": attempt,
                "outcome": outcome,
                "elapsed_s": round(elapsed_s, 3),
                "ts": time.time(),
            }
        )


class GovernedMixin:
    """
    Mix into a NOOA `Agent` subclass to gate every LLM-driven capability behind a
    hard call budget and a bounded, backing-off retry policy -- a circuit breaker,
    not an infinite retry loop.

    Usage:
        class MyAgent(GovernedMixin, Agent, llm=llm):
            def __init__(self):
                super().__init__()
                self.init_governance(max_calls=10, max_retries_per_call=2)

            async def _do_the_llm_thing(self, x: str) -> str:
                '''...'''
                ...

            async def do_the_thing(self, x: str) -> str:
                return await self.governed_call("_do_the_llm_thing", lambda: self._do_the_llm_thing(x))
    """

    def init_governance(
        self, max_calls: int = 20, max_retries_per_call: int = 2, timeout_s: float = 30.0
    ) -> None:
        self._ledger = GovernanceLedger(max_calls=max_calls, max_retries_per_call=max_retries_per_call)
        self._timeout_s = timeout_s

    async def governed_call(self, method_name: str, coro_factory: Callable[[], Awaitable[T]]) -> T:
        """
        Call an LLM-driven capability under budget/retry/timeout enforcement.

        `coro_factory` must be a zero-arg callable that returns a *fresh* awaitable
        each time it's invoked, so a retry actually re-issues the call rather than
        re-awaiting an already-consumed coroutine.
        """
        ledger: GovernanceLedger = self._ledger
        if ledger.remaining_calls() <= 0:
            raise BudgetExceededError(
                f"{method_name}: call budget exhausted ({ledger.calls_made}/{ledger.max_calls})"
            )

        ledger.calls_made += 1
        last_exc: Exception | None = None

        for attempt in range(1, ledger.max_retries_per_call + 2):  # first try + retries
            start = time.monotonic()
            try:
                result = await asyncio.wait_for(coro_factory(), timeout=self._timeout_s)
                ledger.record(method_name, attempt, "success", time.monotonic() - start)
                return result
            except Exception as exc:  # governance layer must catch broadly, by design
                elapsed = time.monotonic() - start
                ledger.record(method_name, attempt, f"error: {exc!r}", elapsed)
                last_exc = exc
                ledger.failures += 1
                if attempt <= ledger.max_retries_per_call:
                    ledger.retries_used += 1
                    await asyncio.sleep(min(2**attempt, 8))  # bounded exponential backoff
                    continue
                raise RetryCircuitOpenError(
                    f"{method_name}: retry circuit open after {attempt} attempts"
                ) from last_exc

        raise last_exc  # unreachable, satisfies type checkers

    def governance_report(self) -> dict[str, Any]:
        """
        Deterministic audit trail: enforcement decisions (budget checks, retries,
        circuit trips), not just the call log NOOA's own tracing already gives you.
        """
        ledger: GovernanceLedger = self._ledger
        return {
            "calls_made": ledger.calls_made,
            "calls_remaining": ledger.remaining_calls(),
            "retries_used": ledger.retries_used,
            "failures": ledger.failures,
            "log": ledger.log,
        }
