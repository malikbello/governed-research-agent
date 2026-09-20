"""
Runs a full checklist template against a subject, item by item, persisting
progress as it goes so the frontend can poll and show live status per item --
the way a real multi-step assessment job should behave, not a single opaque
blocking call.

Readiness scoring is deliberately simple and disclosed, not a black box: it's
documented here so the report explains *why* it landed on a verdict, which
matters more for a due-diligence tool than a fancier-looking but unexplainable
score would.
"""

from __future__ import annotations

from checklist import CheckKind, TEMPLATES
from due_diligence_agent import DueDiligenceAgent
from nvd_lookup import search_nvd

import assessment_store as store


async def run_assessment(assessment_id: str, subject: str, template_key: str, agent: DueDiligenceAgent) -> None:
    template = TEMPLATES[template_key]

    for item in template.items:
        try:
            if item.kind == CheckKind.WEB_RESEARCH:
                claim = item.prompt_template.format(subject=subject)
                verdict = await agent.investigate(claim)
                result = {
                    "domain": item.domain,
                    "verdict": verdict.verdict,
                    "confidence": verdict.confidence,
                    "reasoning": verdict.reasoning,
                    "citations": [c.model_dump() for c in verdict.citations],
                    "scope_note": item.scope_note,
                }
            elif item.kind == CheckKind.NVD_LOOKUP:
                cves = await search_nvd(subject, max_results=5)
                result = {
                    "domain": item.domain,
                    "verdict": "flagged" if cves else "no_known_cves",
                    "confidence": "high" if cves else "medium",
                    "reasoning": (
                        f"Found {len(cves)} publicly disclosed CVE(s)." if cves
                        else "No publicly disclosed CVEs found for this keyword in the NVD."
                    ),
                    "cves": [c.model_dump() for c in cves],
                    "scope_note": item.scope_note,
                }
            else:
                result = {"domain": item.domain, "verdict": "error", "reasoning": "Unknown check kind."}
        except Exception as exc:  # noqa: BLE001 -- one item failing shouldn't abort the whole assessment
            result = {
                "domain": item.domain,
                "verdict": "error",
                "confidence": "low",
                "reasoning": f"This check failed to complete: {exc!r}",
                "scope_note": item.scope_note,
            }

        store.update_item(assessment_id, item.key, result)

    readiness = _score_readiness(assessment_id, template_key)
    store.finalize_assessment(assessment_id, readiness, agent.governance_report())


def _score_readiness(assessment_id: str, template_key: str) -> str:
    """
    Disclosed scoring logic: any item that came back explicitly negative
    (refuted / false / flagged with a HIGH+ severity CVE / error) is a red
    flag. Zero red flags -> "Low risk". 1-2 -> "Needs review". 3+ -> "High risk".
    This is a starting heuristic, not a certified risk model -- shown plainly
    in the report so nobody mistakes it for one.
    """
    record = store.get_assessment(assessment_id)
    if record is None:
        return "Unknown"

    red_flags = 0
    for item_key, entry in record["items"].items():
        result = entry.get("result") or {}
        verdict = result.get("verdict", "")
        if verdict in ("refuted", "false", "error"):
            red_flags += 1
        if verdict == "flagged":
            severities = [c.get("cvss_severity") for c in result.get("cves", [])]
            if any(s in ("HIGH", "CRITICAL") for s in severities):
                red_flags += 1

    if red_flags == 0:
        return "Low risk — no red flags found"
    if red_flags <= 2:
        return f"Needs review — {red_flags} item(s) flagged"
    return f"High risk — {red_flags} item(s) flagged"
