"""
Compatibility shim. The real implementation now lives in `src/nooa_governance/`,
published standalone to PyPI as `nooa-governance` so it's a real, reusable,
independently-installable library -- not just a file inside this demo app.
This module re-exports the same names so the demo code (`research_agent.py`,
`due_diligence_agent.py`, `server.py`) doesn't need to change.
"""

from nooa_governance import (
    BudgetExceededError,
    GovernanceLedger,
    GovernedMixin,
    RetryCircuitOpenError,
)

__all__ = [
    "BudgetExceededError",
    "GovernanceLedger",
    "GovernedMixin",
    "RetryCircuitOpenError",
]
