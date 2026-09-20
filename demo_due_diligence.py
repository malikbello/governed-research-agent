"""
Live test of DueDiligenceAgent -- real web search via Tavily MCP, real citations.
Uses claims where a correct answer genuinely requires current information, not
just training-data recall, to prove the search step is actually doing work.
"""

import asyncio

from due_diligence_agent import DueDiligenceAgent


CLAIMS = [
    "The NVIDIA NOOA agent framework is licensed under Apache-2.0.",
    "The Python package 'nooa-governance' is published on PyPI.",
]


async def main() -> None:
    agent = DueDiligenceAgent(max_calls=5, max_retries_per_call=2)

    for claim in CLAIMS:
        verdict = await agent.investigate(claim)
        print(f"\nCLAIM: {verdict.claim}")
        print(f"  -> {verdict.verdict} ({verdict.confidence} confidence)")
        print(f"  reasoning: {verdict.reasoning}")
        for c in verdict.citations:
            print(f"  citation: [{'supports' if c.supports else 'contradicts'}] {c.url}")
            print(f"            \"{c.quote}\"")

    print("\n--- Governance report ---")
    print(agent.governance_report())


if __name__ == "__main__":
    asyncio.run(main())
