"""PermitTracker FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/permit-tracker", tags=["PermitTracker"])
templates = Jinja2Templates(directory="construction/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "permit-tracker", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["permit_tracker"]


# -- Request models ------------------------------------------------------------

class ProjectCreate(BaseModel):
    project_name: str
    address: str = ""
    lot_number: str = ""
    district: str = ""
    authorized_person: str = ""
    rse: str = ""


class SubmissionCreate(BaseModel):
    project_id: int
    bd_reference: str = ""
    submission_type: str = "GBP"
    minor_works_class: str | None = None
    minor_works_category: str | None = None
    description: str = ""
    submitted_date: str | None = None
    expected_completion: str | None = None


# -- Page ----------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def permit_tracker_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM projects ORDER BY created_at DESC"
        ).fetchall()]
        submissions = [dict(r) for r in conn.execute(
            "SELECT s.*, p.project_name FROM submissions s "
            "LEFT JOIN projects p ON s.project_id = p.id "
            "ORDER BY s.submitted_date DESC"
        ).fetchall()]
        total_submissions = len(submissions)
        active_count = sum(1 for s in submissions if s.get("current_status") not in ("Approved", "Consent Issued", None))
        overdue_count = _count_overdue(submissions, request.app.state.config)
        recent_alerts = [dict(r) for r in conn.execute(
            "SELECT * FROM alerts ORDER BY sent_at DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "permit_tracker/index.html",
        _ctx(
            request,
            projects=projects,
            submissions=submissions,
            total_submissions=total_submissions,
            active_count=active_count,
            overdue_count=overdue_count,
            recent_alerts=recent_alerts,
        ),
    )


def _count_overdue(submissions: list[dict], config: Any) -> int:
    timelines = config.extra.get("permit_tracker", {}).get("expected_timelines", {})
    count = 0
    today = date.today()
    for s in submissions:
        if s.get("current_status") in ("Approved", "Consent Issued", None):
            continue
        if s.get("submitted_date"):
            sub_date = date.fromisoformat(str(s["submitted_date"])[:10])
            stype = s.get("submission_type", "GBP")
            expected_days = timelines.get(stype, 60)
            if (today - sub_date).days > expected_days:
                count += 1
    return count


# -- CRUD ----------------------------------------------------------------------

@router.post("/projects")
async def create_project(request: Request, body: ProjectCreate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO projects (project_name, address, lot_number, district, authorized_person, rse) "
            "VALUES (?,?,?,?,?,?)",
            (body.project_name, body.address, body.lot_number, body.district, body.authorized_person, body.rse),
        )
        project_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="permit-tracker",
        summary=f"Project created: {body.project_name}",
    )
    return {"project_id": project_id}


@router.post("/submissions")
async def create_submission(request: Request, body: SubmissionCreate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO submissions (project_id, bd_reference, submission_type, minor_works_class, "
            "minor_works_category, description, submitted_date, expected_completion, current_status) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (body.project_id, body.bd_reference, body.submission_type, body.minor_works_class,
             body.minor_works_category, body.description, body.submitted_date,
             body.expected_completion, "Received"),
        )
        sub_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO status_history (submission_id, status, status_date) VALUES (?,?,?)",
            (sub_id, "Received", datetime.now().isoformat()),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="permit-tracker",
        summary=f"Submission {body.bd_reference or f'#{sub_id}'} created ({body.submission_type})",
    )
    return {"submission_id": sub_id}


@router.get("/submissions/{sub_id}")
async def get_submission(request: Request, sub_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT s.*, p.project_name FROM submissions s "
            "LEFT JOIN projects p ON s.project_id = p.id WHERE s.id = ?",
            (sub_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Submission not found")
        history = [dict(r) for r in conn.execute(
            "SELECT * FROM status_history WHERE submission_id = ? ORDER BY detected_at",
            (sub_id,),
        ).fetchall()]
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE submission_id = ? ORDER BY uploaded_at DESC",
            (sub_id,),
        ).fetchall()]
    return {**dict(row), "history": history, "documents": docs}


@router.post("/submissions/{sub_id}/check")
async def manual_check(request: Request, sub_id: int) -> dict[str, Any]:
    """Trigger a manual status check for a submission."""
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM submissions WHERE id = ?", (sub_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Submission not found")

    from construction.permit_tracker.monitoring.status_monitor import check_single_submission
    result = await check_single_submission(dict(row), request.app.state)
    return result


@router.post("/documents/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    submission_id: int = 0,
    document_type: str = "correspondence",
) -> dict[str, Any]:
    db = _db(request)
    workspace: Path = request.app.state.workspace
    doc_dir = workspace / "documents" / "permits" / str(submission_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    file_path = doc_dir / (file.filename or "unnamed")
    content = await file.read()
    file_path.write_bytes(content)

    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO documents (submission_id, document_type, file_path, notes) VALUES (?,?,?,?)",
            (submission_id, document_type, str(file_path), ""),
        )
    return {"document_id": cursor.lastrowid, "file_path": str(file_path)}


# -- Partials ------------------------------------------------------------------

@router.get("/partials/gantt", response_class=HTMLResponse)
async def gantt_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        submissions = [dict(r) for r in conn.execute(
            "SELECT s.*, p.project_name FROM submissions s "
            "LEFT JOIN projects p ON s.project_id = p.id "
            "ORDER BY s.submitted_date"
        ).fetchall()]
    return templates.TemplateResponse(
        "permit_tracker/partials/gantt_timeline.html",
        {"request": request, "submissions": submissions, "config": request.app.state.config},
    )


@router.get("/partials/submissions", response_class=HTMLResponse)
async def submissions_partial(request: Request, project_id: int | None = None, status: str | None = None) -> HTMLResponse:
    db = _db(request)
    query = (
        "SELECT s.*, p.project_name FROM submissions s "
        "LEFT JOIN projects p ON s.project_id = p.id WHERE 1=1"
    )
    params: list[Any] = []
    if project_id:
        query += " AND s.project_id = ?"
        params.append(project_id)
    if status:
        query += " AND s.current_status = ?"
        params.append(status)
    query += " ORDER BY s.submitted_date DESC"

    with get_db(db) as conn:
        submissions = [dict(r) for r in conn.execute(query, params).fetchall()]
    return templates.TemplateResponse(
        "permit_tracker/partials/submission_card.html",
        {"request": request, "submissions": submissions, "config": request.app.state.config},
    )


@router.get("/partials/alerts", response_class=HTMLResponse)
async def alerts_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        alerts = [dict(r) for r in conn.execute(
            "SELECT a.*, s.bd_reference, s.submission_type FROM alerts a "
            "LEFT JOIN submissions s ON a.submission_id = s.id "
            "ORDER BY a.sent_at DESC LIMIT 50"
        ).fetchall()]
    return templates.TemplateResponse(
        "permit_tracker/partials/alert_history.html",
        {"request": request, "alerts": alerts},
    )
