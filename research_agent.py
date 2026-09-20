"""
ClaimVerificationAgent: a real task built on GovernedAgent.

Given a claim, it researches and returns a structured, sourced-or-honest verdict.
This task is a meaningful governance testbed on its own merits: verification work
is naturally retry-prone (an ambiguous first answer, a call worth re-issuing with
more care) -- exactly the shape of workload where ungoverned agents rack up
runaway cost and latency in production.
"""

from __future__ import annotations

import os

from nooa import Agent
from nooa.unifiedllm.registry import get_llm_client
from pydantic import BaseModel

from governed_agent import GovernedMixin

MODEL = os.environ.get("NOOA_MODEL", "gemini/gemini-3.5-flash-lite")
llm = get_llm_client(MODEL)

# NOOA injects Anthropic-style `cache_control` markers on the system message by
# default (DEFAULT_CACHE_CONTROL_INJECTION_POINTS). Routed through litellm to
# Gemini, this triggers a Vertex-style context-caching request -- which the
# Gemini free tier rejects outright (TotalCachedContentStorageTokensPerModelFreeTier
# limit=0), turning every single call into a guaranteed failure before the model
# ever runs. Disabling it here is the minimal fix; NOOA doesn't expose this as a
# constructor override, so we set it directly on the client instance.
llm.cache_control_injection_points = []


class Verdict(BaseModel):
    claim: str
    verdict: str  # "supported" | "refuted" | "unclear"
    confidence: str  # "low" | "medium" | "high"
    reasoning: str


class ClaimVerificationAgent(GovernedMixin, Agent, llm=llm):
    """You are a careful fact-checking research assistant. You never state that a claim
    is supported or refuted without a specific, checkable reason grounded in what you
    actually know. 'Unclear' with a stated reason is always preferable to a confident
    guess -- overclaiming certainty is a worse failure than admitting uncertainty."""

    def __init__(self, max_calls: int = 10, max_retries_per_call: int = 2) -> None:
        super().__init__()
        self.init_governance(max_calls=max_calls, max_retries_per_call=max_retries_per_call)

    async def _assess(self, claim: str) -> Verdict:
        """Assess whether the claim is supported, refuted, or unclear, with a confidence
        level (low/medium/high) and specific reasoning. Set claim to the input claim
        verbatim. Do not fabricate certainty you don't have."""
        ...

    async def verify(self, claim: str) -> Verdict:
        """Public, governed entry point. This is the only way this agent's LLM
        capability should ever be invoked -- callers should never call _assess directly,
        since that would bypass budget/retry enforcement entirely."""
        return await self.governed_call("_assess", lambda: self._assess(claim))
