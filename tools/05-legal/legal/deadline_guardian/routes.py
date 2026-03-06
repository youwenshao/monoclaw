"""DeadlineGuardian FastAPI routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from legal.deadline_guardian.business_days import add_calendar_days_with_rollover
from legal.deadline_guardian.calendar_export import export_case_calendar
from legal.deadline_guardian.court_deadlines import calculate_procedural_deadlines
from legal.deadline_guardian.limitation import calculate_limitation
from legal.deadline_guardian.reminder_engine import (
    schedule_reminders,
    update_deadline_statuses,
)

router = APIRouter(prefix="/deadline-guardian", tags=["DeadlineGuardian"])

templates = Jinja2Templates(directory="legal/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "deadline-guardian",
        **extra,
    }


# ── Pydantic models ───────────────────────────────────────────────────────


class CaseCreate(BaseModel):
    case_number: str
    case_name: str
    court: str
    case_type: str
    client_name: str
    solicitor_responsible: str


class DeadlineCreate(BaseModel):
    case_id: int
    deadline_type: str
    description: str
    due_date: str | None = None
    trigger_event: str | None = None
    trigger_date: str | None = None
    statutory_basis: str | None = None
    notes: str | None = None
    auto_reminders: bool = True
    reminder_intervals: list[int] = [30, 14, 7, 3, 1]


# ── Main page ──────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def deadline_guardian_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["deadline_guardian"]
    update_deadline_statuses(db)

    with get_db(db) as conn:
        cases = [dict(r) for r in conn.execute(
            "SELECT * FROM cases WHERE status = 'active' ORDER BY created_date DESC"
        ).fetchall()]

        overdue = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE status = 'overdue'"
        ).fetchone()[0]
        due_soon = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE status = 'due_soon'"
        ).fetchone()[0]
        total_active = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE status IN ('upcoming','due_soon','overdue')"
        ).fetchone()[0]

        urgent_deadlines = [dict(r) for r in conn.execute(
            """SELECT d.*, c.case_number, c.case_name, c.solicitor_responsible
               FROM deadlines d
               JOIN cases c ON d.case_id = c.id
               WHERE d.status IN ('overdue', 'due_soon', 'upcoming')
               ORDER BY d.due_date ASC LIMIT 20"""
        ).fetchall()]

    return templates.TemplateResponse(
        "deadline_guardian/index.html",
        _ctx(
            request,
            cases=cases,
            overdue_count=overdue,
            due_soon_count=due_soon,
            total_active=total_active,
            urgent_deadlines=urgent_deadlines,
        ),
    )


# ── Cases ──────────────────────────────────────────────────────────────────


@router.post("/cases")
async def create_case(request: Request, body: CaseCreate) -> dict[str, Any]:
    db = request.app.state.db_paths["deadline_guardian"]

    with get_db(db) as conn:
        existing = conn.execute(
            "SELECT id FROM cases WHERE case_number = ?", (body.case_number,)
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Case {body.case_number} already exists",
            )

        cursor = conn.execute(
            """INSERT INTO cases
               (case_number, case_name, court, case_type,
                client_name, solicitor_responsible)
               VALUES (?,?,?,?,?,?)""",
            (
                body.case_number, body.case_name, body.court,
                body.case_type, body.client_name, body.solicitor_responsible,
            ),
        )
        case_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="deadline-guardian",
        summary=f"New case created: {body.case_number} — {body.case_name}",
    )

    return {"case_id": case_id, "case_number": body.case_number, "status": "active"}


# ── Deadlines ──────────────────────────────────────────────────────────────


@router.post("/deadlines")
async def create_deadline(request: Request, body: DeadlineCreate) -> dict[str, Any]:
    db = request.app.state.db_paths["deadline_guardian"]
    holidays = request.app.state.config.extra.get("public_holidays") or None

    with get_db(db) as conn:
        case = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (body.case_id,)
        ).fetchone()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    case_data = dict(case)

    if body.trigger_event and body.trigger_date:
        trigger = date.fromisoformat(body.trigger_date)
        procedural = calculate_procedural_deadlines(
            body.trigger_event, trigger, case_data["court"], holidays
        )

        created: list[dict] = []
        with get_db(db) as conn:
            for dl in procedural:
                cursor = conn.execute(
                    """INSERT INTO deadlines
                       (case_id, deadline_type, description, due_date,
                        trigger_date, statutory_basis, status, notes)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (
                        body.case_id, dl["deadline_type"], dl["description"],
                        dl["due_date"], dl["trigger_date"], dl["statutory_basis"],
                        "upcoming", body.notes,
                    ),
                )
                dl_id = cursor.lastrowid
                if body.auto_reminders:
                    schedule_reminders(
                        dl_id,
                        date.fromisoformat(dl["due_date"]),
                        body.reminder_intervals,
                        db,
                    )
                created.append({"deadline_id": dl_id, **dl})

        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="deadline-guardian",
            summary=(
                f"Auto-calculated {len(created)} deadlines "
                f"for {case_data['case_number']}"
            ),
        )
        return {"case_id": body.case_id, "deadlines": created}

    if not body.due_date:
        raise HTTPException(
            status_code=400,
            detail="Either due_date or trigger_event+trigger_date required",
        )

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO deadlines
               (case_id, deadline_type, description, due_date,
                trigger_date, statutory_basis, status, notes)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                body.case_id, body.deadline_type, body.description,
                body.due_date, body.trigger_date, body.statutory_basis,
                "upcoming", body.notes,
            ),
        )
        dl_id = cursor.lastrowid

    if body.auto_reminders:
        schedule_reminders(
            dl_id,
            date.fromisoformat(body.due_date),
            body.reminder_intervals,
            db,
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="deadline-guardian",
        summary=f"Deadline added: {body.deadline_type} for {case_data['case_number']}",
    )

    return {"deadline_id": dl_id, "due_date": body.due_date, "status": "upcoming"}


# ── Limitation calculator ──────────────────────────────────────────────────


@router.get("/calculate")
async def calculate_limitation_period(
    request: Request,
    ordinance: str,
    accrual_date: str,
) -> dict[str, Any]:
    holidays = request.app.state.config.extra.get("public_holidays") or None

    try:
        accrual = date.fromisoformat(accrual_date)
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD."
        )

    try:
        result = calculate_limitation(ordinance, accrual, holidays)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return result


# ── Complete deadline ──────────────────────────────────────────────────────


@router.post("/deadlines/{deadline_id}/complete")
async def complete_deadline(
    request: Request, deadline_id: int
) -> dict[str, Any]:
    db = request.app.state.db_paths["deadline_guardian"]
    now = datetime.now().isoformat()

    with get_db(db) as conn:
        dl = conn.execute(
            "SELECT * FROM deadlines WHERE id = ?", (deadline_id,)
        ).fetchone()
        if not dl:
            raise HTTPException(status_code=404, detail="Deadline not found")
        dl_data = dict(dl)

        conn.execute(
            "UPDATE deadlines SET status = 'completed', completed_date = ? WHERE id = ?",
            (now, deadline_id),
        )

        case = conn.execute(
            "SELECT case_number FROM cases WHERE id = ?", (dl_data["case_id"],)
        ).fetchone()

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="deadline-guardian",
        summary=(
            f"Deadline completed: {dl_data['deadline_type']} "
            f"({dict(case)['case_number']})"
        ),
    )

    return {
        "deadline_id": deadline_id,
        "status": "completed",
        "completed_date": now,
    }


# ── Audit trail ────────────────────────────────────────────────────────────


@router.get("/audit/{case_id}")
async def audit_trail(request: Request, case_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["deadline_guardian"]

    with get_db(db) as conn:
        case = conn.execute(
            "SELECT * FROM cases WHERE id = ?", (case_id,)
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        deadlines = [dict(r) for r in conn.execute(
            "SELECT * FROM deadlines WHERE case_id = ? ORDER BY due_date ASC",
            (case_id,),
        ).fetchall()]

        deadline_ids = [d["id"] for d in deadlines]
        reminders: list[dict] = []
        if deadline_ids:
            placeholders = ",".join("?" * len(deadline_ids))
            reminders = [dict(r) for r in conn.execute(
                f"SELECT * FROM reminders WHERE deadline_id IN ({placeholders}) "  # noqa: S608
                "ORDER BY reminder_date ASC",
                deadline_ids,
            ).fetchall()]

    return {
        "case": dict(case),
        "deadlines": deadlines,
        "reminders": reminders,
        "total_deadlines": len(deadlines),
        "completed": sum(1 for d in deadlines if d["status"] == "completed"),
        "overdue": sum(1 for d in deadlines if d["status"] == "overdue"),
    }


# ── Calendar export ────────────────────────────────────────────────────────


@router.get("/calendar/export/{case_id}")
async def calendar_export(request: Request, case_id: int) -> Response:
    db = request.app.state.db_paths["deadline_guardian"]

    try:
        ics_bytes = export_case_calendar(case_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    with get_db(db) as conn:
        case = conn.execute(
            "SELECT case_number FROM cases WHERE id = ?", (case_id,)
        ).fetchone()

    safe_number = dict(case)["case_number"].replace("/", "-").replace(" ", "_")
    filename = f"deadlines_{safe_number}.ics"

    return Response(
        content=ics_bytes,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── HTMX Partials ─────────────────────────────────────────────────────────


@router.get("/deadline-card/partial", response_class=HTMLResponse)
async def deadline_card_partial(
    request: Request,
    case_id: int | None = None,
    status: str | None = None,
) -> HTMLResponse:
    db = request.app.state.db_paths["deadline_guardian"]
    update_deadline_statuses(db)

    query = """SELECT d.*, c.case_number, c.case_name, c.solicitor_responsible
               FROM deadlines d
               JOIN cases c ON d.case_id = c.id
               WHERE 1=1"""
    params: list[Any] = []

    if case_id:
        query += " AND d.case_id = ?"
        params.append(case_id)
    if status and status != "all":
        query += " AND d.status = ?"
        params.append(status)

    query += " ORDER BY d.due_date ASC LIMIT 50"

    with get_db(db) as conn:
        deadlines = [dict(r) for r in conn.execute(query, params).fetchall()]

    return templates.TemplateResponse(
        "deadline_guardian/partials/deadline_card.html",
        {"request": request, "deadlines": deadlines},
    )


@router.get("/calendar/partial", response_class=HTMLResponse)
async def calendar_partial(
    request: Request, month: str | None = None
) -> HTMLResponse:
    db = request.app.state.db_paths["deadline_guardian"]

    if month:
        year_s, m_s = month.split("-")
        year, m = int(year_s), int(m_s)
        start = f"{year}-{m:02d}-01"
        if m == 12:
            end = f"{year + 1}-01-01"
        else:
            end = f"{year}-{m + 1:02d}-01"
    else:
        today = date.today()
        start = today.replace(day=1).isoformat()
        if today.month == 12:
            end = today.replace(year=today.year + 1, month=1, day=1).isoformat()
        else:
            end = today.replace(month=today.month + 1, day=1).isoformat()

    with get_db(db) as conn:
        deadlines = [dict(r) for r in conn.execute(
            """SELECT d.*, c.case_number, c.case_name
               FROM deadlines d
               JOIN cases c ON d.case_id = c.id
               WHERE d.due_date >= ? AND d.due_date < ?
               ORDER BY d.due_date ASC""",
            (start, end),
        ).fetchall()]

    return templates.TemplateResponse(
        "deadline_guardian/partials/calendar.html",
        {"request": request, "deadlines": deadlines, "month": month or start[:7]},
    )


@router.get("/audit-trail/partial", response_class=HTMLResponse)
async def audit_trail_partial(request: Request, case_id: int) -> HTMLResponse:
    data = await audit_trail(request, case_id)
    return templates.TemplateResponse(
        "deadline_guardian/partials/audit_trail.html",
        {"request": request, **data},
    )
