# Governed Research Agent

An object-oriented cost/retry/timeout governance layer for [NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) (NVIDIA's Object-Oriented Agents framework), demonstrated with a real claim-verification agent.

## The problem

Agentic AI cost governance is a real, documented production problem — not a hypothetical one. A June 2026 preprint catalogued **63 LLM-agent budget-overrun incidents across 21 orchestration frameworks**, with uncontrolled retry loops identified as a leading cause. Real incidents in the wild: agents that retry a failed call, silently escalate to a more expensive model, and burn hundreds of dollars overnight with no human checkpoint.

Every fix on the market today — [agent-gov](https://dev.to/sschelliah/announcing-agent-gov-open-source-ai-agent-cost-governance-nj9), LiteLLM's per-key budgets, Microsoft's Agent Governance Toolkit — works as a **reverse proxy**: external infrastructure sitting between the agent and the LLM provider, invisible to and untestable alongside the agent's own code.

## The idea

NOOA agents are plain Python classes — fields are state, methods are capabilities, docstrings are prompts, `...`-body methods become LLM-driven at runtime. That object-oriented design makes a different answer to cost governance possible: **bake it into the agent's own class**, as an ordinary, inheritable, unit-testable Python mixin — not a network gateway nobody in the codebase can see.

`GovernedMixin` (`governed_agent.py`) gives any NOOA agent:
- A hard **call budget**, enforced *before* any LLM spend happens — not after.
- A bounded, backing-off **retry policy** — a real circuit breaker, not an infinite loop.
- A **timeout** per call.
- A deterministic **audit trail** of every governed call: attempt count, outcome, latency.

Governance logic is ordinary, deterministic Python — never delegated to the LLM — so it holds regardless of what the model decides to do.

## The demo agent

`ClaimVerificationAgent` (`research_agent.py`) is a real task, not a toy wrapper: given a claim, it returns a structured verdict (supported / refuted / unclear) with a confidence level and reasoning. Verification work is naturally retry-prone — a meaningful testbed for the governance layer, not an arbitrary choice.

`demo.py` runs it against three claims (including one deliberately false claim, to check the agent actually disagrees rather than rubber-stamping a plausible-sounding wrong statement), prints the governance audit trail, and separately proves the budget guard actually refuses a call once the budget is spent — not just that happy-path calls succeed.

## Platform note

NOOA's storage layer imports `fcntl`, a Unix-only module — **it does not run on native Windows Python.** This project is set up to run under WSL (or any Linux/macOS environment). See `.venv-linux/` for the WSL-side virtual environment.

## Setup

```bash
# Inside WSL / Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # fill in your own GEMINI_API_KEY
python demo.py
```

## Why this exists

Built as a hands-on recreation exploring NOOA (released Aug 2026, NVIDIA-labs) the same week it was found — the governance angle ties directly into a broader open question around agentic-system reliability in production (see the author's separate `agent-harness-reliability-benchmark` project), and demonstrates that pattern with a real, working, inheritable base class rather than just describing it.
