"""ClientPortal Bot FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/client-portal", tags=["ClientPortal"])

templates = Jinja2Templates(directory="immigration/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "client-portal", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def client_portal_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["client_portal"]
    today = date.today().isoformat()

    with get_db(db) as conn:
        cases = [dict(r) for r in conn.execute(
            "SELECT * FROM cases ORDER BY created_at DESC"
        ).fetchall()]
        active_count = conn.execute(
            "SELECT COUNT(*) FROM cases WHERE current_status NOT IN ('visa_label_issued', 'entry_made', 'hkid_applied')"
        ).fetchone()[0]
        awaiting_docs = conn.execute(
            "SELECT COUNT(*) FROM outstanding_documents WHERE received = 0 AND deadline >= ?",
            (today,),
        ).fetchone()[0]
        week_from = today
        week_to = (date.today() + timedelta(days=7)).isoformat()
        week_appointments = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE datetime >= ? AND datetime < ? AND status = 'confirmed'",
            (week_from, week_to),
        ).fetchone()[0]
        unread_msgs = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE escalated = 1"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "client_portal/index.html",
        _ctx(
            request,
            cases=cases,
            active_count=active_count,
            awaiting_docs=awaiting_docs,
            week_appointments=week_appointments,
            unread_msgs=unread_msgs,
        ),
    )


# ── Cases ──────────────────────────────────────────────────────────────────

@router.get("/cases")
async def list_cases(request: Request, status: str | None = None) -> list[dict]:
    db = request.app.state.db_paths["client_portal"]
    query = "SELECT * FROM cases"
    params: list[Any] = []
    if status:
        query += " WHERE current_status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC"
    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


class CreateCaseRequest(BaseModel):
    client_name: str
    client_phone: str | None = None
    client_telegram_id: str | None = None
    scheme: str
    consultant_name: str | None = None
    language_pref: str = "en"


@router.post("/cases")
async def create_case(request: Request, body: CreateCaseRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]
    import random
    import string
    ref = f"IM-{date.today().year}-{random.randint(100, 999)}"

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO cases
               (reference_code, client_name, client_phone, client_telegram_id,
                scheme, consultant_name, language_pref, status_updated_at)
               VALUES (?,?,?,?,?,?,?,?)""",
            (ref, body.client_name, body.client_phone, body.client_telegram_id,
             body.scheme, body.consultant_name, body.language_pref,
             datetime.now().isoformat()),
        )
        case_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO status_history (case_id, status, notes) VALUES (?,?,?)",
            (case_id, "documents_gathering", "Case created"),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="client-portal",
        summary=f"New case {ref} created for {body.client_name} ({body.scheme})",
    )

    return {"case_id": case_id, "reference_code": ref}


# ── Status ─────────────────────────────────────────────────────────────────

class UpdateStatusRequest(BaseModel):
    status: str
    notes: str | None = None
    notify_client: bool = True


@router.post("/cases/{case_id}/status")
async def update_case_status(request: Request, case_id: int, body: UpdateStatusRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    case = dict(row)
    now = datetime.now().isoformat()

    with get_db(db) as conn:
        conn.execute(
            "UPDATE cases SET current_status = ?, status_updated_at = ? WHERE id = ?",
            (body.status, now, case_id),
        )
        conn.execute(
            "INSERT INTO status_history (case_id, status, notes, notified_client) VALUES (?,?,?,?)",
            (case_id, body.status, body.notes, body.notify_client),
        )

    if body.notify_client:
        from immigration.client_portal.status.milestones import notify_milestone
        notify_milestone(request.app.state, case, body.status)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="client-portal",
        summary=f"Case {case['reference_code']} status → {body.status}",
    )

    return {"case_id": case_id, "new_status": body.status}


# ── Timeline ───────────────────────────────────────────────────────────────

@router.get("/cases/{case_id}/timeline")
async def case_timeline(request: Request, case_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]
    with get_db(db) as conn:
        case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        history = [dict(r) for r in conn.execute(
            "SELECT * FROM status_history WHERE case_id = ? ORDER BY changed_at ASC",
            (case_id,),
        ).fetchall()]
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM outstanding_documents WHERE case_id = ? ORDER BY deadline",
            (case_id,),
        ).fetchall()]

    return {"case": dict(case), "history": history, "outstanding_documents": docs}


# ── Messages ───────────────────────────────────────────────────────────────

@router.get("/messages/{case_id}")
async def get_messages(request: Request, case_id: int, limit: int = 50) -> list[dict]:
    db = request.app.state.db_paths["client_portal"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM conversations WHERE case_id = ? ORDER BY timestamp DESC LIMIT ?",
            (case_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


class SendMessageRequest(BaseModel):
    case_id: int
    channel: str = "whatsapp"
    message_text: str


@router.post("/messages/send")
async def send_message(request: Request, body: SendMessageRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]

    with get_db(db) as conn:
        case = conn.execute("SELECT * FROM cases WHERE id = ?", (body.case_id,)).fetchone()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    case_data = dict(case)

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO conversations (case_id, channel, sender, message_text)
               VALUES (?,?,?,?)""",
            (body.case_id, body.channel, "consultant", body.message_text),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="client-portal",
        summary=f"Message sent to {case_data['client_name']} via {body.channel}",
    )

    return {"status": "sent", "channel": body.channel}


# ── Broadcast ──────────────────────────────────────────────────────────────

class BroadcastRequest(BaseModel):
    case_ids: list[int]
    message_text: str
    channel: str = "whatsapp"


@router.post("/broadcast")
async def broadcast_message(request: Request, body: BroadcastRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]
    sent = 0

    for case_id in body.case_ids:
        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO conversations (case_id, channel, sender, message_text)
                   VALUES (?,?,?,?)""",
                (case_id, body.channel, "consultant_broadcast", body.message_text),
            )
        sent += 1

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="client-portal",
        summary=f"Broadcast sent to {sent} clients via {body.channel}",
    )

    return {"sent": sent, "total": len(body.case_ids)}


# ── Webhook (Twilio WhatsApp incoming) ─────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    form = await request.form()
    from_number = form.get("From", "")
    message_body = form.get("Body", "")

    from immigration.client_portal.bot.router import handle_incoming_message
    response = await handle_incoming_message(request.app.state, str(from_number), str(message_body), "whatsapp")

    return {"status": "processed", "response": response}


# ── Appointments ───────────────────────────────────────────────────────────

@router.get("/appointments/available")
async def available_slots(request: Request, date_str: str | None = None) -> dict[str, Any]:
    from immigration.client_portal.appointments.booking import get_available_slots
    config = request.app.state.config
    target_date = date.fromisoformat(date_str) if date_str else date.today() + timedelta(days=1)
    slots = get_available_slots(
        target_date,
        config.extra.get("business_hours", "09:00-18:00"),
        config.extra.get("saturday_hours", "09:00-13:00"),
        config.extra.get("public_holidays", []),
    )
    return {"date": target_date.isoformat(), "slots": slots}


class BookAppointmentRequest(BaseModel):
    case_id: int
    datetime_str: str
    duration_minutes: int = 60
    type: str = "consultation"
    notes: str | None = None


@router.post("/appointments/book")
async def book_appointment(request: Request, body: BookAppointmentRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["client_portal"]

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO appointments (case_id, datetime, duration_minutes, type, notes)
               VALUES (?,?,?,?,?)""",
            (body.case_id, body.datetime_str, body.duration_minutes, body.type, body.notes),
        )
        appt_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="client-portal",
        summary=f"Appointment booked for case #{body.case_id} on {body.datetime_str}",
    )

    return {"appointment_id": appt_id, "status": "confirmed"}


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/case-table/partial", response_class=HTMLResponse)
async def case_table_partial(request: Request, status_filter: str | None = None) -> HTMLResponse:
    db = request.app.state.db_paths["client_portal"]
    query = "SELECT * FROM cases"
    params: list[Any] = []
    if status_filter and status_filter != "all":
        query += " WHERE current_status = ?"
        params.append(status_filter)
    query += " ORDER BY created_at DESC"
    with get_db(db) as conn:
        cases = [dict(r) for r in conn.execute(query, params).fetchall()]
    return templates.TemplateResponse(
        "client_portal/partials/case_table.html",
        {"request": request, "cases": cases},
    )


@router.get("/case-timeline/partial", response_class=HTMLResponse)
async def case_timeline_partial(request: Request, case_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["client_portal"]
    with get_db(db) as conn:
        case = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
        history = [dict(r) for r in conn.execute(
            "SELECT * FROM status_history WHERE case_id = ? ORDER BY changed_at ASC",
            (case_id,),
        ).fetchall()]
    return templates.TemplateResponse(
        "client_portal/partials/case_timeline.html",
        {"request": request, "case": dict(case) if case else {}, "history": history},
    )
