"""SiteCoordinator FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/site-coordinator", tags=["SiteCoordinator"])
templates = Jinja2Templates(directory="construction/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "site-coordinator", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["site_coordinator"]


# -- Request models ------------------------------------------------------------

class AssignmentCreate(BaseModel):
    site_id: int
    contractor_id: int
    assignment_date: str
    start_time: str = "08:00"
    end_time: str = "18:00"
    scope_of_work: str = ""
    trade: str = ""
    priority: int = 5
    depends_on: int | None = None


class AssignmentStatusUpdate(BaseModel):
    status: str
    completion_notes: str = ""


class DeliveryCreate(BaseModel):
    site_id: int
    supplier: str = ""
    description: str = ""
    expected_date: str = ""
    expected_time: str = ""


class AccessLogEntry(BaseModel):
    site_id: int
    person_name: str
    company: str = ""
    action: str = "sign_in"


# -- Page ----------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def site_coordinator_page(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    with get_db(db) as conn:
        sites = [dict(r) for r in conn.execute(
            "SELECT * FROM sites WHERE status = 'active' ORDER BY site_name"
        ).fetchall()]
        contractors = [dict(r) for r in conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE ORDER BY company_name"
        ).fetchall()]
        week_assignments = [dict(r) for r in conn.execute(
            "SELECT sa.*, s.site_name, c.company_name, c.trade AS contractor_trade "
            "FROM schedule_assignments sa "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "LEFT JOIN contractors c ON sa.contractor_id = c.id "
            "WHERE sa.assignment_date BETWEEN ? AND ? ORDER BY sa.assignment_date, sa.start_time",
            (week_start.isoformat(), week_end.isoformat()),
        ).fetchall()]
        today_count = sum(1 for a in week_assignments if str(a.get("assignment_date", ""))[:10] == today.isoformat())
        active_contractors = len(set(a["contractor_id"] for a in week_assignments if a.get("contractor_id")))

    config = request.app.state.config
    typhoon_mode = config.extra.get("site_coordinator", {}).get("typhoon_mode", False)

    return templates.TemplateResponse(
        "site_coordinator/index.html",
        _ctx(
            request,
            sites=sites,
            contractors=contractors,
            week_assignments=week_assignments,
            today_count=today_count,
            active_contractors=active_contractors,
            typhoon_mode=typhoon_mode,
            week_start=week_start.isoformat(),
            week_end=week_end.isoformat(),
        ),
    )


# -- Assignments ---------------------------------------------------------------

@router.post("/assignments")
async def create_assignment(request: Request, body: AssignmentCreate) -> dict[str, Any]:
    db = _db(request)

    from construction.site_coordinator.scheduling.conflict_detector import check_conflicts
    conflicts = check_conflicts(db, body.contractor_id, body.site_id, body.assignment_date, body.trade)
    if conflicts:
        return {"error": "conflicts", "details": conflicts}

    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO schedule_assignments (site_id, contractor_id, assignment_date, start_time, "
            "end_time, scope_of_work, trade, priority, depends_on) VALUES (?,?,?,?,?,?,?,?,?)",
            (body.site_id, body.contractor_id, body.assignment_date, body.start_time,
             body.end_time, body.scope_of_work, body.trade, body.priority, body.depends_on),
        )
        assignment_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="site-coordinator",
        summary=f"Assignment #{assignment_id} created for {body.assignment_date} ({body.trade})",
    )
    return {"assignment_id": assignment_id}


@router.post("/assignments/{assignment_id}/status")
async def update_assignment_status(request: Request, assignment_id: int, body: AssignmentStatusUpdate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM schedule_assignments WHERE id = ?", (assignment_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Assignment not found")
        extra_fields = ""
        extra_params: list[Any] = []
        if body.status == "completed":
            extra_fields = ", completed_at = ?, completion_notes = ?"
            extra_params = [datetime.now().isoformat(), body.completion_notes]
        elif body.status == "dispatched":
            extra_fields = ", dispatched_at = ?"
            extra_params = [datetime.now().isoformat()]

        conn.execute(
            f"UPDATE schedule_assignments SET status = ?{extra_fields} WHERE id = ?",
            [body.status] + extra_params + [assignment_id],
        )
    return {"assignment_id": assignment_id, "status": body.status}


# -- Optimization --------------------------------------------------------------

@router.post("/optimize")
async def optimize_schedule(request: Request, target_date: str = Form("")) -> dict[str, Any]:
    if not target_date:
        target_date = date.today().isoformat()

    from construction.site_coordinator.scheduling.optimizer import optimize_day
    result = optimize_day(_db(request), target_date, request.app.state.config)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="site-coordinator",
        summary=f"Schedule optimized for {target_date}: {result.get('assignments_created', 0)} assignments",
    )
    return result


# -- Dispatch ------------------------------------------------------------------

@router.post("/dispatch/send")
async def send_dispatch(request: Request, dispatch_date: str = Form("")) -> dict[str, Any]:
    if not dispatch_date:
        dispatch_date = (date.today() + timedelta(days=1)).isoformat()

    from construction.site_coordinator.dispatch.whatsapp_dispatcher import dispatch_assignments
    result = await dispatch_assignments(_db(request), dispatch_date, request.app.state)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="site-coordinator",
        summary=f"Dispatch sent for {dispatch_date}: {result.get('messages_sent', 0)} messages",
    )
    return result


# -- Typhoon mode --------------------------------------------------------------

@router.post("/typhoon-mode")
async def toggle_typhoon_mode(request: Request) -> dict[str, Any]:
    config = request.app.state.config
    sc_config = config.extra.setdefault("site_coordinator", {})
    current = sc_config.get("typhoon_mode", False)
    sc_config["typhoon_mode"] = not current

    if not current:
        from construction.site_coordinator.scheduling.calendar_manager import reschedule_for_typhoon
        result = reschedule_for_typhoon(_db(request), date.today().isoformat())
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="alert",
            tool_name="site-coordinator",
            summary=f"Typhoon mode ACTIVATED — {result.get('rescheduled', 0)} assignments rescheduled",
            requires_human_action=True,
        )
    else:
        result = {"typhoon_mode": False}
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="info",
            tool_name="site-coordinator",
            summary="Typhoon mode deactivated",
        )

    return {"typhoon_mode": not current, **result}


# -- WhatsApp webhook ----------------------------------------------------------

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    from construction.site_coordinator.dispatch.progress_collector import handle_incoming
    form = await request.form()
    await handle_incoming(dict(form), request.app.state)
    return {"status": "ok"}


# -- Partials ------------------------------------------------------------------

@router.get("/partials/schedule", response_class=HTMLResponse)
async def schedule_partial(request: Request, week_start: str | None = None) -> HTMLResponse:
    db = _db(request)
    if not week_start:
        today = date.today()
        ws = today - timedelta(days=today.weekday())
    else:
        ws = date.fromisoformat(week_start)
    we = ws + timedelta(days=6)

    with get_db(db) as conn:
        assignments = [dict(r) for r in conn.execute(
            "SELECT sa.*, s.site_name, c.company_name "
            "FROM schedule_assignments sa "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "LEFT JOIN contractors c ON sa.contractor_id = c.id "
            "WHERE sa.assignment_date BETWEEN ? AND ? ORDER BY sa.assignment_date, sa.start_time",
            (ws.isoformat(), we.isoformat()),
        ).fetchall()]
        contractors = [dict(r) for r in conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE ORDER BY company_name"
        ).fetchall()]
    return templates.TemplateResponse(
        "site_coordinator/partials/schedule_grid.html",
        {"request": request, "assignments": assignments, "contractors": contractors,
         "week_start": ws.isoformat(), "week_end": we.isoformat()},
    )


@router.get("/partials/map", response_class=HTMLResponse)
async def map_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        sites = [dict(r) for r in conn.execute(
            "SELECT * FROM sites WHERE status = 'active' AND latitude IS NOT NULL"
        ).fetchall()]
    return templates.TemplateResponse(
        "site_coordinator/partials/resource_dashboard.html",
        {"request": request, "sites": sites},
    )


@router.get("/partials/dispatch-log", response_class=HTMLResponse)
async def dispatch_log_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        dispatched = [dict(r) for r in conn.execute(
            "SELECT sa.*, s.site_name, c.company_name, c.whatsapp_number "
            "FROM schedule_assignments sa "
            "LEFT JOIN sites s ON sa.site_id = s.id "
            "LEFT JOIN contractors c ON sa.contractor_id = c.id "
            "WHERE sa.dispatched_at IS NOT NULL ORDER BY sa.dispatched_at DESC LIMIT 30"
        ).fetchall()]
    return templates.TemplateResponse(
        "site_coordinator/partials/dispatch_log.html",
        {"request": request, "dispatched": dispatched},
    )


@router.get("/partials/deliveries", response_class=HTMLResponse)
async def deliveries_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "site_coordinator/partials/delivery_schedule.html",
        {"request": request, "deliveries": []},
    )


@router.get("/partials/access-log", response_class=HTMLResponse)
async def access_log_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "site_coordinator/partials/site_access_log.html",
        {"request": request, "entries": []},
    )
