"""
Demo: run ClaimVerificationAgent against a small set of claims -- including one
deliberately false claim drawn from this project's own portfolio research, as a
real test of whether the agent actually refutes a plausible-sounding wrong claim
rather than agreeing with it -- and print the governance audit trail alongside
the verdicts.
"""

import asyncio

from governed_agent import BudgetExceededError
from research_agent import ClaimVerificationAgent

CLAIMS = [
    "NVIDIA released NOOA, a single-class Python agent framework, in August 2026.",
    "GitHub exposes a public REST API endpoint for changing a user's profile avatar image.",
    "The Elliptic Bitcoin dataset is heterophilous because illicit transactions are usually "
    "connected to other illicit transactions.",
]


async def main() -> None:
    agent = ClaimVerificationAgent(max_calls=5, max_retries_per_call=2)

    for claim in CLAIMS:
        verdict = await agent.verify(claim)
        print(f"\nCLAIM: {verdict.claim}")
        print(f"  -> {verdict.verdict} ({verdict.confidence} confidence): {verdict.reasoning}")

    print("\n--- Governance report ---")
    report = agent.governance_report()
    print(f"Calls made: {report['calls_made']} / remaining: {report['calls_remaining']}")
    print(f"Retries used: {report['retries_used']} / failures: {report['failures']}")
    for entry in report["log"]:
        print(f"  {entry}")

    # Prove the circuit breaker actually fires, not just that happy-path calls work.
    print("\n--- Budget enforcement check (max_calls=1, agent already used its call) ---")
    tiny_budget_agent = ClaimVerificationAgent(max_calls=1, max_retries_per_call=1)
    await tiny_budget_agent.verify(CLAIMS[0])  # uses the one allowed call
    try:
        await tiny_budget_agent.verify(CLAIMS[1])  # should be refused, not silently billed
        print("FAIL: second call should have been refused by the budget guard.")
    except BudgetExceededError as exc:
        print(f"OK: budget guard correctly refused the call before any LLM spend: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
