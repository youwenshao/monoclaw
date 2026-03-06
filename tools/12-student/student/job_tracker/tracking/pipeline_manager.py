"""Kanban pipeline management for job applications."""

from __future__ import annotations

import json
from pathlib import Path

from openclaw_shared.database import get_db

STAGES = [
    "saved", "applied", "phone_screen", "assessment",
    "interview", "final_round", "offer", "accepted",
    "rejected", "withdrawn",
]


def get_kanban_data(db_path: str | Path) -> dict:
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT a.*, j.title, j.company, j.salary_min, j.salary_max, j.job_type
               FROM applications a
               LEFT JOIN job_listings j ON a.job_id = j.id
               ORDER BY a.created_at DESC"""
        ).fetchall()

    columns: dict[str, list[dict]] = {stage: [] for stage in STAGES}
    for row in rows:
        app = dict(row)
        stage = app.get("stage", "saved")
        if stage not in columns:
            stage = "saved"

        app["skills_required"] = _safe_json(app.get("skills_required"))
        app["missing_keywords"] = _safe_json(app.get("missing_keywords"))

        created = app.get("created_at", "")
        if created:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                delta = datetime.now() - dt.replace(tzinfo=None)
                app["days_in_stage"] = delta.days
            except (ValueError, TypeError):
                app["days_in_stage"] = 0
        else:
            app["days_in_stage"] = 0

        columns[stage].append(app)

    return columns


def update_stage(application_id: int, new_stage: str, db_path: str | Path) -> None:
    if new_stage not in STAGES:
        raise ValueError(f"Invalid stage: {new_stage}")

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM applications WHERE id = ?", (application_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"Application {application_id} not found")

        if new_stage == "applied":
            conn.execute(
                """UPDATE applications
                   SET stage = ?, applied_date = COALESCE(applied_date, DATE('now'))
                   WHERE id = ?""",
                (new_stage, application_id),
            )
        elif new_stage in ("phone_screen", "assessment", "interview", "final_round", "offer"):
            conn.execute(
                """UPDATE applications
                   SET stage = ?, response_date = COALESCE(response_date, DATE('now'))
                   WHERE id = ?""",
                (new_stage, application_id),
            )
        else:
            conn.execute(
                "UPDATE applications SET stage = ? WHERE id = ?",
                (new_stage, application_id),
            )


def get_stage_counts(db_path: str | Path) -> dict[str, int]:
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT stage, COUNT(*) as cnt FROM applications GROUP BY stage"
        ).fetchall()
    counts = {stage: 0 for stage in STAGES}
    for row in rows:
        counts[row["stage"]] = row["cnt"]
    return counts


def _safe_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val
