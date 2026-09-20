"""
Production-facing HTTP layer: serves both pages (product + engineering console)
and exposes the governed agent and assessment runner over a small JSON API.
Kept separate from governed_agent.py/due_diligence_agent.py deliberately --
the governance and agent logic have zero HTTP/web dependencies, so they stay
independently unit-testable.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import assessment_store as store
from assessment_runner import run_assessment
from checklist import TEMPLATES
from due_diligence_agent import DueDiligenceAgent
from governed_agent import BudgetExceededError, RetryCircuitOpenError

app = FastAPI(title="Governed Research Agent")

FRONTEND_DIR = Path(__file__).parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

store.init_db()

# One agent per process, budget shared across requests and across assessment
# runs -- deliberately, so the console can actually demonstrate the budget
# guard tripping over real, sustained use, the same way a real long-running
# service would exhaust a real budget. Uses DueDiligenceAgent (real web search
# + citations via Tavily MCP, plus NVD lookups in the checklist runner).
agent = DueDiligenceAgent(max_calls=100, max_retries_per_call=2)


class VerifyRequest(BaseModel):
    claim: str


class NewAssessmentRequest(BaseModel):
    subject: str
    template_key: str


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/")
def index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "product.html")


@app.get("/console")
def console() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "console.html")


# --- Product API: due-diligence assessments -----------------------------------


@app.get("/api/templates")
def list_templates() -> dict:
    return {
        key: {
            "label": t.label,
            "description": t.description,
            "items": [{"key": i.key, "label": i.label, "domain": i.domain, "scope_note": i.scope_note} for i in t.items],
        }
        for key, t in TEMPLATES.items()
    }


@app.post("/api/assessments")
async def create_assessment(req: NewAssessmentRequest, background_tasks: BackgroundTasks) -> dict:
    if not req.subject.strip():
        raise HTTPException(status_code=400, detail="subject must not be empty")
    if req.template_key not in TEMPLATES:
        raise HTTPException(status_code=400, detail=f"unknown template_key: {req.template_key}")

    template = TEMPLATES[req.template_key]
    item_keys = [i.key for i in template.items]
    assessment_id = store.create_assessment(req.subject.strip(), req.template_key, item_keys)

    async def _run() -> None:
        try:
            await run_assessment(assessment_id, req.subject.strip(), req.template_key, agent)
        except (BudgetExceededError, RetryCircuitOpenError) as exc:
            store.fail_assessment(assessment_id, str(exc))

    # FastAPI's BackgroundTasks natively awaits async callables -- the earlier
    # version wrapped this in `lambda: asyncio.create_task(_run())`, which is a
    # real bug: it creates a fire-and-forget task with no reference kept beyond
    # the lambda call, which risks the task being garbage-collected before it
    # completes (a classic asyncio pitfall). Passing the coroutine function
    # directly lets FastAPI own and await it properly.
    background_tasks.add_task(_run)
    return {"id": assessment_id}


@app.get("/api/assessments")
def list_assessments() -> list[dict]:
    return store.list_assessments()


@app.get("/api/assessments/{assessment_id}")
def get_assessment(assessment_id: str) -> dict:
    record = store.get_assessment(assessment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="assessment not found")
    return record


# --- Console API: raw governed-agent access, kept for the engineering page ----


@app.get("/api/governance")
def governance() -> dict:
    return agent.governance_report()


@app.post("/api/verify")
async def verify(req: VerifyRequest) -> dict:
    if not req.claim.strip():
        raise HTTPException(status_code=400, detail="claim must not be empty")

    try:
        verdict = await agent.investigate(req.claim)
        return {"ok": True, "verdict": verdict.model_dump(), "governance": agent.governance_report()}
    except BudgetExceededError as exc:
        return {"ok": False, "error": "budget_exceeded", "detail": str(exc), "governance": agent.governance_report()}
    except RetryCircuitOpenError as exc:
        return {"ok": False, "error": "circuit_open", "detail": str(exc), "governance": agent.governance_report()}


if __name__ == "__main__":
    import os

    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
