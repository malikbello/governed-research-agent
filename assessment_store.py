"""
SQLite-backed storage for due-diligence assessment runs -- so a report survives
a server restart and there's a real history view, the way an actual internal
tool would need, instead of an in-memory dict that vanishes on redeploy.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(__file__).parent / "assessments.db"


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assessments (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                template_key TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                readiness TEXT,
                items_json TEXT NOT NULL,
                governance_json TEXT NOT NULL
            )
            """
        )


def create_assessment(subject: str, template_key: str, item_keys: list[str]) -> str:
    assessment_id = str(uuid.uuid4())
    now = time.time()
    items = {k: {"status": "pending", "result": None} for k in item_keys}
    with _conn() as conn:
        conn.execute(
            "INSERT INTO assessments (id, subject, template_key, status, created_at, updated_at, readiness, items_json, governance_json) "
            "VALUES (?, ?, ?, 'running', ?, ?, NULL, ?, ?)",
            (assessment_id, subject, template_key, now, now, json.dumps(items), json.dumps({})),
        )
    return assessment_id


def update_item(assessment_id: str, item_key: str, result: dict[str, Any]) -> None:
    with _conn() as conn:
        row = conn.execute("SELECT items_json FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
        if row is None:
            return
        items = json.loads(row["items_json"])
        items[item_key] = {"status": "done", "result": result}
        conn.execute(
            "UPDATE assessments SET items_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(items), time.time(), assessment_id),
        )


def finalize_assessment(assessment_id: str, readiness: str, governance: dict[str, Any]) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE assessments SET status = 'complete', readiness = ?, governance_json = ?, updated_at = ? WHERE id = ?",
            (readiness, json.dumps(governance), time.time(), assessment_id),
        )


def fail_assessment(assessment_id: str, error: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE assessments SET status = 'failed', readiness = ?, updated_at = ? WHERE id = ?",
            (error, time.time(), assessment_id),
        )


def get_assessment(assessment_id: str) -> dict[str, Any] | None:
    with _conn() as conn:
        row = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
        if row is None:
            return None
        return {
            "id": row["id"],
            "subject": row["subject"],
            "template_key": row["template_key"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "readiness": row["readiness"],
            "items": json.loads(row["items_json"]),
            "governance": json.loads(row["governance_json"]),
        }


def list_assessments(limit: int = 50) -> list[dict[str, Any]]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT id, subject, template_key, status, created_at, readiness FROM assessments "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
