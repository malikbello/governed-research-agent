"""
Minimal API-key auth for the cost-consuming endpoints.

Scoped deliberately: this protects the endpoints that spend the governed
agent's budget (starting an assessment, a raw /api/verify call) -- not every
GET endpoint, since read-only access to a report or the template list carries
no cost or abuse risk on its own. A real multi-tenant production deployment
would want broader auth (per-user API keys, rate limiting per key, not just a
single shared secret) -- this is the minimum real version, not the final one.

If API_KEY is unset, auth is disabled and a loud warning is logged -- this
keeps local/demo use frictionless without silently shipping an unauthenticated
production deployment. Set API_KEY before deploying anywhere reachable by
anyone other than you.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import Header, HTTPException

logger = logging.getLogger("security")

_API_KEY = os.environ.get("API_KEY", "")

if not _API_KEY:
    logger.warning(
        "API_KEY is not set -- the cost-consuming endpoints (/api/assessments, /api/verify) "
        "are UNAUTHENTICATED. This is fine for local development, but set API_KEY before "
        "deploying anywhere reachable by anyone other than you."
    )


async def require_api_key(x_api_key: str = Header(default="")) -> None:
    if not _API_KEY:
        return  # auth disabled -- local/demo mode, warned above
    if not secrets.compare_digest(x_api_key, _API_KEY):
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Key header")
