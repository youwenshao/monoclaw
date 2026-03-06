"""TaxCalendar Bot FastAPI routes."""

from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/tax-calendar", tags=["TaxCalendar"])

templates = Jinja2Templates(directory="accounting/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "tax-calendar", **extra}


def _db(request: Request):
    return request.app.state.db_paths["tax_calendar"]


def _traffic_light(deadline: dict) -> str:
    """Return traffic-light colour based on filing status and proximity to due date."""
    if deadline["filing_status"] in ("filed", "submitted"):
        return "green"
    effective_due = deadline.get("extended_due_date") or deadline["original_due_date"]
    if isinstance(effective_due, str):
        effective_due = date.fromisoformat(effective_due)
    days_left = (effective_due - date.today()).days
    if days_left < 0:
        return "red"
    if days_left <= 14:
        return "amber"
    return "green"


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def tax_calendar_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        total_clients = conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        upcoming = conn.execute(
            """SELECT COUNT(*) FROM deadlines
               WHERE filing_status NOT IN ('filed','submitted')
                 AND COALESCE(extended_due_date, original_due_date) >= DATE('now')
                 AND COALESCE(extended_due_date, original_due_date) <= DATE('now', '+30 days')""",
        ).fetchone()[0]
        overdue = conn.execute(
            """SELECT COUNT(*) FROM deadlines
               WHERE filing_status NOT IN ('filed','submitted')
                 AND COALESCE(extended_due_date, original_due_date) < DATE('now')""",
        ).fetchone()[0]
        filed = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE filing_status IN ('filed','submitted')",
        ).fetchone()[0]

    return templates.TemplateResponse(
        "tax_calendar/index.html",
        _ctx(
            request,
            total_clients=total_clients,
            upcoming=upcoming,
            overdue=overdue,
            filed=filed,
        ),
    )


# ── Full-year calendar JSON ───────────────────────────────────────────────

@router.get("/calendar")
async def calendar_data(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               ORDER BY COALESCE(d.extended_due_date, d.original_due_date)"""
        ).fetchall()

    events = []
    for r in rows:
        d = dict(r)
        effective_due = d.get("extended_due_date") or d["original_due_date"]
        events.append({
            "id": d["id"],
            "title": f"{d['company_name']} – {d.get('form_code', d['deadline_type'])}",
            "date": effective_due,
            "color": _traffic_light(d),
            "deadline_type": d["deadline_type"],
            "filing_status": d["filing_status"],
        })
    return events


# ── Countdown cards ───────────────────────────────────────────────────────

@router.get("/upcoming")
async def upcoming_deadlines(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name, c.assigned_accountant
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               WHERE d.filing_status NOT IN ('filed','submitted')
                 AND COALESCE(d.extended_due_date, d.original_due_date) >= ?
               ORDER BY COALESCE(d.extended_due_date, d.original_due_date) ASC
               LIMIT 3""",
            (today,),
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        effective_due = d.get("extended_due_date") or d["original_due_date"]
        if isinstance(effective_due, str):
            effective_due = date.fromisoformat(effective_due)
        days_left = (effective_due - date.today()).days
        result.append({
            **d,
            "effective_due_date": effective_due.isoformat(),
            "days_left": days_left,
            "color": _traffic_light(d),
        })
    return result


# ── Clients ───────────────────────────────────────────────────────────────

@router.get("/clients")
async def list_clients(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT c.*,
                      COUNT(d.id) AS total_deadlines,
                      SUM(CASE WHEN d.filing_status IN ('filed','submitted') THEN 1 ELSE 0 END) AS filed_count,
                      SUM(CASE WHEN d.filing_status NOT IN ('filed','submitted')
                                AND COALESCE(d.extended_due_date, d.original_due_date) < DATE('now') THEN 1 ELSE 0 END) AS overdue_count
               FROM clients c
               LEFT JOIN deadlines d ON d.client_id = c.id
               GROUP BY c.id
               ORDER BY c.company_name"""
        ).fetchall()
    return [dict(r) for r in rows]


class AddClientRequest(BaseModel):
    company_name: str
    br_number: str | None = None
    year_end_month: int
    ird_file_number: str | None = None
    company_type: str = "corporation"
    assigned_accountant: str | None = None
    accountant_phone: str | None = None
    partner: str | None = None
    partner_phone: str | None = None
    mpf_scheme: str | None = None
    notes: str | None = None


@router.post("/clients")
async def add_client(
    request: Request,
    body: AddClientRequest | None = None,
    file: UploadFile | None = File(None),
) -> dict[str, Any]:
    db = _db(request)

    if file and file.filename and file.filename.endswith(".csv"):
        content = (await file.read()).decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        imported = 0
        with get_db(db) as conn:
            for row in reader:
                conn.execute(
                    """INSERT INTO clients
                       (company_name, br_number, year_end_month, ird_file_number,
                        company_type, assigned_accountant, accountant_phone,
                        partner, partner_phone, mpf_scheme, notes)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        row.get("company_name", ""),
                        row.get("br_number"),
                        int(row.get("year_end_month", 3)),
                        row.get("ird_file_number"),
                        row.get("company_type", "corporation"),
                        row.get("assigned_accountant"),
                        row.get("accountant_phone"),
                        row.get("partner"),
                        row.get("partner_phone"),
                        row.get("mpf_scheme"),
                        row.get("notes"),
                    ),
                )
                imported += 1

        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="tax-calendar",
            summary=f"Bulk imported {imported} clients from CSV",
        )
        return {"imported": imported}

    if not body:
        raise HTTPException(status_code=400, detail="Provide JSON body or CSV file")

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO clients
               (company_name, br_number, year_end_month, ird_file_number,
                company_type, assigned_accountant, accountant_phone,
                partner, partner_phone, mpf_scheme, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body.company_name, body.br_number, body.year_end_month,
                body.ird_file_number, body.company_type, body.assigned_accountant,
                body.accountant_phone, body.partner, body.partner_phone,
                body.mpf_scheme, body.notes,
            ),
        )
        client_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tax-calendar",
        summary=f"Client added: {body.company_name}",
    )
    return {"client_id": client_id, "company_name": body.company_name}


@router.get("/clients/{client_id}")
async def client_detail(request: Request, client_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Client not found")
        client = dict(row)
        deadlines = [dict(r) for r in conn.execute(
            "SELECT * FROM deadlines WHERE client_id = ? ORDER BY original_due_date",
            (client_id,),
        ).fetchall()]
        mpf = [dict(r) for r in conn.execute(
            "SELECT * FROM mpf_deadlines WHERE client_id = ? ORDER BY period_month DESC",
            (client_id,),
        ).fetchall()]

    for d in deadlines:
        d["color"] = _traffic_light(d)

    client["deadlines"] = deadlines
    client["mpf_deadlines"] = mpf
    return client


# ── Deadlines ─────────────────────────────────────────────────────────────

@router.get("/deadlines")
async def list_deadlines(
    request: Request,
    status: str | None = None,
    client_id: int | None = None,
    deadline_type: str | None = None,
) -> list[dict[str, Any]]:
    db = _db(request)
    conditions: list[str] = []
    params: list[Any] = []

    if status:
        conditions.append("d.filing_status = ?")
        params.append(status)
    if client_id:
        conditions.append("d.client_id = ?")
        params.append(client_id)
    if deadline_type:
        conditions.append("d.deadline_type = ?")
        params.append(deadline_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_db(db) as conn:
        rows = conn.execute(
            f"""SELECT d.*, c.company_name, c.assigned_accountant
                FROM deadlines d
                JOIN clients c ON c.id = d.client_id
                {where}
                ORDER BY COALESCE(d.extended_due_date, d.original_due_date)""",
            params,
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        d["color"] = _traffic_light(d)
        result.append(d)
    return result


@router.get("/deadlines/{deadline_id}")
async def deadline_detail(request: Request, deadline_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            """SELECT d.*, c.company_name, c.assigned_accountant, c.partner
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               WHERE d.id = ?""",
            (deadline_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Deadline not found")
        d = dict(row)

        checklist_row = conn.execute(
            "SELECT * FROM checklists WHERE deadline_id = ? ORDER BY id DESC LIMIT 1",
            (deadline_id,),
        ).fetchone()

    d["color"] = _traffic_light(d)
    d["checklist"] = dict(checklist_row) if checklist_row else None
    if d["checklist"] and d["checklist"].get("items"):
        try:
            d["checklist"]["items"] = json.loads(d["checklist"]["items"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


class UpdateFilingStatusRequest(BaseModel):
    filing_status: str
    submitted_date: str | None = None


@router.post("/deadlines/{deadline_id}/status")
async def update_filing_status(
    request: Request, deadline_id: int, body: UpdateFilingStatusRequest
) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT d.*, c.company_name FROM deadlines d JOIN clients c ON c.id = d.client_id WHERE d.id = ?",
            (deadline_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Deadline not found")
        prev = dict(row)

        conn.execute(
            "UPDATE deadlines SET filing_status = ?, submitted_date = ? WHERE id = ?",
            (body.filing_status, body.submitted_date, deadline_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tax-calendar",
        summary=f"{prev['company_name']} {prev.get('form_code','')} status → {body.filing_status}",
    )
    return {"deadline_id": deadline_id, "filing_status": body.filing_status}


class RecordExtensionRequest(BaseModel):
    extension_type: str
    extended_due_date: str
    extension_status: str = "applied"


@router.post("/deadlines/{deadline_id}/extension")
async def record_extension(
    request: Request, deadline_id: int, body: RecordExtensionRequest
) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT d.*, c.company_name FROM deadlines d JOIN clients c ON c.id = d.client_id WHERE d.id = ?",
            (deadline_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Deadline not found")
        prev = dict(row)

        conn.execute(
            """UPDATE deadlines
               SET extension_type = ?, extended_due_date = ?, extension_status = ?
               WHERE id = ?""",
            (body.extension_type, body.extended_due_date, body.extension_status, deadline_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tax-calendar",
        summary=(
            f"Extension recorded for {prev['company_name']} {prev.get('form_code','')}: "
            f"{body.extension_type} → {body.extended_due_date}"
        ),
    )
    return {
        "deadline_id": deadline_id,
        "extension_type": body.extension_type,
        "extended_due_date": body.extended_due_date,
        "extension_status": body.extension_status,
    }


# ── Checklists ────────────────────────────────────────────────────────────

@router.get("/checklists/{deadline_id}")
async def get_checklist(request: Request, deadline_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM checklists WHERE deadline_id = ? ORDER BY id DESC LIMIT 1",
            (deadline_id,),
        ).fetchone()

    if not row:
        from accounting.tax_calendar.checklists.generator import generate_checklist
        with get_db(db) as conn:
            dl = conn.execute("SELECT * FROM deadlines WHERE id = ?", (deadline_id,)).fetchone()
        if not dl:
            raise HTTPException(status_code=404, detail="Deadline not found")
        checklist = generate_checklist(dict(dl))
        with get_db(db) as conn:
            conn.execute(
                "INSERT INTO checklists (deadline_id, total_items, completed_items, items) VALUES (?,?,?,?)",
                (deadline_id, checklist["total_items"], 0, json.dumps(checklist["items"])),
            )
            row = conn.execute(
                "SELECT * FROM checklists WHERE deadline_id = ? ORDER BY id DESC LIMIT 1",
                (deadline_id,),
            ).fetchone()

    result = dict(row)
    if result.get("items"):
        try:
            result["items"] = json.loads(result["items"])
        except (json.JSONDecodeError, TypeError):
            pass
    return result


class ToggleChecklistRequest(BaseModel):
    item_index: int


@router.post("/checklists/{deadline_id}/toggle")
async def toggle_checklist_item(
    request: Request, deadline_id: int, body: ToggleChecklistRequest
) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM checklists WHERE deadline_id = ? ORDER BY id DESC LIMIT 1",
            (deadline_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Checklist not found")

        checklist = dict(row)
        items = json.loads(checklist["items"]) if isinstance(checklist["items"], str) else checklist["items"]

        if body.item_index < 0 or body.item_index >= len(items):
            raise HTTPException(status_code=400, detail="Invalid item index")

        items[body.item_index]["done"] = not items[body.item_index].get("done", False)
        completed = sum(1 for it in items if it.get("done"))

        conn.execute(
            "UPDATE checklists SET items = ?, completed_items = ? WHERE id = ?",
            (json.dumps(items), completed, checklist["id"]),
        )

    return {"deadline_id": deadline_id, "items": items, "completed_items": completed}


# ── MPF ───────────────────────────────────────────────────────────────────

@router.get("/mpf")
async def mpf_tracker(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT m.*, c.company_name
               FROM mpf_deadlines m
               JOIN clients c ON c.id = m.client_id
               ORDER BY m.contribution_due_date DESC"""
        ).fetchall()

    result = []
    for r in rows:
        d = dict(r)
        due = date.fromisoformat(d["contribution_due_date"])
        if d["paid"]:
            d["status"] = "paid"
        elif due < date.today():
            d["status"] = "overdue"
        else:
            d["status"] = "pending"
        result.append(d)
    return result


# ── Compliance report ─────────────────────────────────────────────────────

@router.get("/report")
async def compliance_report(request: Request) -> dict[str, Any]:
    db = _db(request)
    today = date.today()
    month_start = today.replace(day=1).isoformat()
    month_end = ((today.replace(day=1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)).isoformat()

    with get_db(db) as conn:
        total_deadlines = conn.execute("SELECT COUNT(*) FROM deadlines").fetchone()[0]
        filed_count = conn.execute(
            "SELECT COUNT(*) FROM deadlines WHERE filing_status IN ('filed','submitted')"
        ).fetchone()[0]
        overdue_count = conn.execute(
            """SELECT COUNT(*) FROM deadlines
               WHERE filing_status NOT IN ('filed','submitted')
                 AND COALESCE(extended_due_date, original_due_date) < DATE('now')"""
        ).fetchone()[0]
        this_month = conn.execute(
            """SELECT COUNT(*) FROM deadlines
               WHERE COALESCE(extended_due_date, original_due_date) BETWEEN ? AND ?""",
            (month_start, month_end),
        ).fetchone()[0]
        by_type = {
            row[0]: {"total": row[1], "filed": row[2]}
            for row in conn.execute(
                """SELECT deadline_type, COUNT(*),
                          SUM(CASE WHEN filing_status IN ('filed','submitted') THEN 1 ELSE 0 END)
                   FROM deadlines GROUP BY deadline_type"""
            ).fetchall()
        }
        by_accountant = [
            {"accountant": row[0], "total": row[1], "filed": row[2], "overdue": row[3]}
            for row in conn.execute(
                """SELECT c.assigned_accountant, COUNT(d.id),
                          SUM(CASE WHEN d.filing_status IN ('filed','submitted') THEN 1 ELSE 0 END),
                          SUM(CASE WHEN d.filing_status NOT IN ('filed','submitted')
                                    AND COALESCE(d.extended_due_date, d.original_due_date) < DATE('now') THEN 1 ELSE 0 END)
                   FROM deadlines d
                   JOIN clients c ON c.id = d.client_id
                   GROUP BY c.assigned_accountant"""
            ).fetchall()
        ]

    return {
        "period": f"{month_start} to {month_end}",
        "total_deadlines": total_deadlines,
        "filed": filed_count,
        "overdue": overdue_count,
        "due_this_month": this_month,
        "compliance_rate": round(filed_count / total_deadlines * 100, 1) if total_deadlines else 0,
        "by_type": by_type,
        "by_accountant": by_accountant,
    }


# ── ICS export ────────────────────────────────────────────────────────────

@router.get("/export-ics")
async def export_ics(request: Request) -> StreamingResponse:
    from icalendar import Calendar, Event as IcsEvent

    db = _db(request)
    cal = Calendar()
    cal.add("prodid", "-//OpenClaw TaxCalendar//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", "Tax Calendar")

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id"""
        ).fetchall()

    for r in rows:
        d = dict(r)
        effective_due = d.get("extended_due_date") or d["original_due_date"]
        if isinstance(effective_due, str):
            effective_due = date.fromisoformat(effective_due)

        ev = IcsEvent()
        ev.add("summary", f"{d['company_name']} – {d.get('form_code', d['deadline_type'])}")
        ev.add("dtstart", effective_due)
        ev.add("dtend", effective_due)
        ev.add("description", f"Filing status: {d['filing_status']}\nAssessment year: {d.get('assessment_year','')}")
        ev["uid"] = f"openclaw-tax-{d['id']}@accounting"
        cal.add_component(ev)

    buf = io.BytesIO(cal.to_ical())
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="text/calendar",
        headers={"Content-Disposition": "attachment; filename=tax_calendar.ics"},
    )


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/calendar/partial", response_class=HTMLResponse)
async def calendar_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               ORDER BY COALESCE(d.extended_due_date, d.original_due_date)"""
        ).fetchall()

    deadlines = []
    for r in rows:
        d = dict(r)
        d["color"] = _traffic_light(d)
        d["effective_due_date"] = d.get("extended_due_date") or d["original_due_date"]
        deadlines.append(d)

    return templates.TemplateResponse(
        "tax_calendar/partials/calendar_grid.html",
        {"request": request, "deadlines": deadlines},
    )


@router.get("/countdown/partial", response_class=HTMLResponse)
async def countdown_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.company_name, c.assigned_accountant
               FROM deadlines d
               JOIN clients c ON c.id = d.client_id
               WHERE d.filing_status NOT IN ('filed','submitted')
                 AND COALESCE(d.extended_due_date, d.original_due_date) >= ?
               ORDER BY COALESCE(d.extended_due_date, d.original_due_date) ASC
               LIMIT 3""",
            (today,),
        ).fetchall()

    cards = []
    for r in rows:
        d = dict(r)
        effective_due = d.get("extended_due_date") or d["original_due_date"]
        if isinstance(effective_due, str):
            effective_due = date.fromisoformat(effective_due)
        d["days_left"] = (effective_due - date.today()).days
        d["color"] = _traffic_light(d)
        cards.append(d)

    return templates.TemplateResponse(
        "tax_calendar/partials/countdown_cards.html",
        {"request": request, "cards": cards},
    )
