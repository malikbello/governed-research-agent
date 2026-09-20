"""
Direct NVD (National Vulnerability Database) API integration -- a deterministic
Python tool, not an MCP server, since NVD's REST API is simple enough that a
dedicated subprocess/MCP server would be pure overhead. This matches NOOA's own
tool philosophy (methods as tools) rather than reaching for MCP by default.

Confirmed directly against the live API before writing this: no API key required
for basic keyword search, base URL and response shape verified with a real
request (CVE-2008-7261 test query), not assumed from memory.
"""

from __future__ import annotations

import httpx
from pydantic import BaseModel

NVD_BASE_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"


class CVEResult(BaseModel):
    cve_id: str
    description: str
    cvss_severity: str | None
    cvss_score: float | None
    published: str
    references: list[str]


async def search_nvd(keyword: str, max_results: int = 5) -> list[CVEResult]:
    """Search the NVD for known vulnerabilities matching a keyword (e.g. a
    product or vendor name). Returns the most relevant/recent results."""
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            NVD_BASE_URL,
            params={"keywordSearch": keyword, "resultsPerPage": max_results},
        )
        resp.raise_for_status()
        data = resp.json()

    results: list[CVEResult] = []
    for item in data.get("vulnerabilities", []):
        cve = item.get("cve", {})
        descriptions = cve.get("descriptions", [])
        description = next((d["value"] for d in descriptions if d.get("lang") == "en"), "")

        metrics = cve.get("metrics", {})
        severity = None
        score = None
        for metric_key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
            if metric_key in metrics and metrics[metric_key]:
                m = metrics[metric_key][0]
                severity = m.get("baseSeverity") or m.get("cvssData", {}).get("baseSeverity")
                score = m.get("cvssData", {}).get("baseScore")
                break

        references = [r.get("url", "") for r in cve.get("references", [])][:5]

        results.append(
            CVEResult(
                cve_id=cve.get("id", "UNKNOWN"),
                description=description,
                cvss_severity=severity,
                cvss_score=score,
                published=cve.get("published", ""),
                references=references,
            )
        )
    return results
