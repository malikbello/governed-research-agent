# nooa-governance

Object-oriented cost, retry, and timeout governance for [NOOA](https://github.com/NVIDIA-NeMo/labs-OO-Agents) agents — baked into the agent's own class, not bolted on as an external proxy.

## Why

A June 2026 preprint catalogued 63 LLM-agent budget-overrun incidents across 21 orchestration frameworks, with uncontrolled retry loops as a leading cause. Every existing fix (agent-gov, LiteLLM per-key budgets, Microsoft's Agent Governance Toolkit) works as a reverse proxy sitting between the agent and the LLM provider — external, opaque to the agent's own codebase, untestable alongside the agent's own logic.

NOOA agents are plain Python classes. That makes a different answer possible: governance as an ordinary, inheritable, unit-testable mixin, living in the same codebase as the agent it governs.

## Install

```bash
pip install nooa-governance
```

## Usage

```python
from nooa import Agent
from nooa.unifiedllm.registry import get_llm_client
from nooa_governance import GovernedMixin

llm = get_llm_client("gemini/gemini-3.5-flash-lite")

class MyAgent(GovernedMixin, Agent, llm=llm):
    def __init__(self):
        super().__init__()
        self.init_governance(max_calls=10, max_retries_per_call=2, timeout_s=30.0)

    async def _do_the_llm_thing(self, x: str) -> str:
        """..."""
        ...

    async def do_the_thing(self, x: str) -> str:
        return await self.governed_call("_do_the_llm_thing", lambda: self._do_the_llm_thing(x))
```

Every governed call is checked against a hard call budget *before* any LLM spend happens, retried a bounded number of times with exponential backoff on failure, and time-limited per attempt — never delegated to the LLM, so enforcement holds no matter what the model decides to do. `agent.governance_report()` gives a deterministic audit trail: calls made, retries used, failures, and a per-attempt log.

## What this doesn't do (yet)

`calls_made` counts governed method invocations, not raw LLM API calls — NOOA's execution strategy can make more than one real model round-trip per method call, so this is a solid retry/circuit-breaker mechanism but an imperfect proxy for exact dollar cost. A future version should hook into NOOA's own tracing or LiteLLM's token-usage callbacks for precise cost accounting.

## Full example

A complete, real application built on this library — a claim/due-diligence verification agent with a live dashboard, Docker, and Kubernetes manifests — is in the same repository: [github.com/HonTime2023/governed-research-agent](https://github.com/HonTime2023/governed-research-agent).

## License

Apache-2.0
