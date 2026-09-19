"""
Production-facing HTTP layer: serves the dashboard and exposes the governed
agent over a small JSON API. Kept separate from governed_agent.py/research_agent.py
deliberately -- the governance logic has zero HTTP/web dependencies, so it stays
independently unit-testable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from governed_agent import BudgetExceededError, RetryCircuitOpenError
from research_agent import ClaimVerificationAgent

app = FastAPI(title="Governed Research Agent")

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# One agent per process, budget shared across requests -- deliberately, so the
# dashboard can actually demonstrate the budget guard tripping across multiple
# demo calls, the same way a real long-running service would exhaust a real budget.
agent = ClaimVerificationAgent(max_calls=15, max_retries_per_call=2)


class VerifyRequest(BaseModel):
    claim: str


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/api/governance")
def governance() -> dict:
    return agent.governance_report()


@app.post("/api/verify")
def verify(req: VerifyRequest) -> dict:
    import asyncio

    if not req.claim.strip():
        raise HTTPException(status_code=400, detail="claim must not be empty")

    try:
        verdict = asyncio.run(agent.verify(req.claim))
        return {"ok": True, "verdict": verdict.model_dump(), "governance": agent.governance_report()}
    except BudgetExceededError as exc:
        return {"ok": False, "error": "budget_exceeded", "detail": str(exc), "governance": agent.governance_report()}
    except RetryCircuitOpenError as exc:
        return {"ok": False, "error": "circuit_open", "detail": str(exc), "governance": agent.governance_report()}


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
