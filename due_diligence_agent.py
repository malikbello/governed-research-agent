"""
DueDiligenceAgent: the enterprise-grade upgrade to ClaimVerificationAgent.

The previous agent answered from the model's training knowledge alone -- no
internet, no tools, nothing that could actually fail in an interesting way.
This one does real due diligence the way it should be done: search the live
web (via Tavily's official MCP server), read the actual results, and verify
a claim with real citations -- exactly the workflow this project's own
research has run by hand, dozens of times, to check GitHub star counts,
license terms, and dataset claims before locking anything in.

This is also the point where governance stops being decorative: a real web
search can time out, rate-limit, or return nothing useful, so the retry/
budget/circuit-breaker logic in governed_agent.py is now protecting against
real, common failure modes, not a hypothetical one.
"""

from __future__ import annotations

import os
from pathlib import Path

from nooa import Agent
from nooa.mcp import MCPManager, MCPTool
from nooa.unifiedllm.registry import get_llm_client
from pydantic import BaseModel

from governed_agent import GovernedMixin

MODEL = os.environ.get("NOOA_MODEL", "gemini/gemini-3.5-flash-lite")
llm = get_llm_client(MODEL)
llm.cache_control_injection_points = []  # see research_agent.py for why

MCP_CONFIG = Path(__file__).parent / ".mcp.json"


class Citation(BaseModel):
    url: str
    supports: bool  # does this specific source support or contradict the claim?
    quote: str  # the specific relevant snippet, not a paraphrase


class DueDiligenceVerdict(BaseModel):
    claim: str
    verdict: str  # "supported" | "refuted" | "unclear"
    confidence: str  # "low" | "medium" | "high"
    reasoning: str
    citations: list[Citation]


class DueDiligenceAgent(GovernedMixin, Agent, llm=llm):
    """You are an enterprise due-diligence research agent. Your job is verifying
    claims about software, vendors, datasets, licenses, and technical facts using
    real, current web sources -- never from memory alone, since your training data
    has a cutoff and claims about recent releases, current star counts, or current
    licensing terms can be stale or simply wrong by the time anyone asks you.

    Ground rules you must follow on every claim:
    - Always search before answering. Never skip straight to reasoning from what
      you already "know" -- that's exactly the failure mode this agent exists to
      avoid.
    - Every citation must include a real URL and a specific quoted snippet from
      that source, not a paraphrase and not a fabricated quote.
    - If search results are genuinely inconclusive, say so -- 'unclear' with a
      clear explanation of what's missing is always preferable to a confident
      guess dressed up with citations that don't actually support it.
    """

    search: MCPTool

    def __init__(self, max_calls: int = 10, max_retries_per_call: int = 2) -> None:
        super().__init__()
        self.init_governance(max_calls=max_calls, max_retries_per_call=max_retries_per_call, timeout_s=45.0)
        self.search = MCPManager.create_from_server("tavily", mcp_file=MCP_CONFIG)

    async def _investigate(self, claim: str) -> DueDiligenceVerdict:
        """Search the web for evidence about this claim, then verify it using
        only what the search actually returned. Set claim to the input claim
        verbatim. Include at least one real citation with a real URL and a real
        quoted snippet -- if search turns up nothing useful, say so in reasoning
        and set verdict to 'unclear' rather than inventing a citation."""
        ...

    async def investigate(self, claim: str) -> DueDiligenceVerdict:
        """Public, governed entry point. This is the only way this agent's
        LLM/tool capability should ever be invoked -- callers should never call
        _investigate directly, since that would bypass budget/retry enforcement."""
        return await self.governed_call("_investigate", lambda: self._investigate(claim))
