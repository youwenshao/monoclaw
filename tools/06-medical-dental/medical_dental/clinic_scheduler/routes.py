"""ClinicScheduler FastAPI routes — appointments, walk-ins, waitlist, WhatsApp webhook."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from medical_dental.clinic_scheduler.bot.reminder_sender import ReminderSender
from medical_dental.clinic_scheduler.bot.whatsapp_handler import WhatsAppBookingHandler
from medical_dental.clinic_scheduler.scheduling.availability import AvailabilityEngine
from medical_dental.clinic_scheduler.scheduling.booking_engine import (
    BookingConflictError,
    BookingEngine,
    InvalidTransitionError,
    StaleVersionError,
)
from medical_dental.clinic_scheduler.scheduling.waitlist import WaitlistManager
from medical_dental.clinic_scheduler.scheduling.walk_in_queue import WalkInQueue

router = APIRouter(prefix="/clinic-scheduler", tags=["ClinicScheduler"])

templates = Jinja2Templates(directory="medical_dental/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "clinic-scheduler",
        **extra,
    }


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["clinic_scheduler"])


def _mona(request: Request) -> str:
    return str(request.app.state.db_paths["mona_events"])


def _config(request: Request) -> Any:
    return request.app.state.config


def _availability(request: Request) -> AvailabilityEngine:
    cfg = _config(request)
    return AvailabilityEngine(
        holidays=cfg.extra.get("public_holidays", []),
        config_durations=cfg.extra.get("appointment_durations", {}),
    )


def _booking_engine() -> BookingEngine:
    return BookingEngine()


def _waitlist_mgr() -> WaitlistManager:
    return WaitlistManager()


def _walk_in(request: Request) -> WalkInQueue:
    cfg = _config(request)
    return WalkInQueue(service_durations=cfg.extra.get("appointment_durations"))


def _reminder(request: Request) -> ReminderSender:
    cfg = _config(request)
    messaging = getattr(request.app.state, "messaging", None)
    return ReminderSender(
        messaging=messaging,
        clinic_address=cfg.extra.get("clinic_address", ""),
        default_language=cfg.messaging.default_language,
    )


# ── Dashboard page ─────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def scheduler_page(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        doctors = [dict(r) for r in conn.execute(
            "SELECT * FROM doctors WHERE active = 1 ORDER BY name_en"
        ).fetchall()]
        today_appts = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE appointment_date = ?",
            (today,),
        ).fetchone()[0]
        today_confirmed = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE appointment_date = ? AND status = 'confirmed'",
            (today,),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "clinic_scheduler/index.html",
        _ctx(
            request,
            doctors=doctors,
            today_appts=today_appts,
            today_confirmed=today_confirmed,
        ),
    )


# ── Doctors ────────────────────────────────────────────────────────────────


@router.get("/api/doctors")
async def list_doctors(request: Request) -> list[dict[str, Any]]:
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            "SELECT * FROM doctors WHERE active = 1 ORDER BY name_en"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/api/doctors/{doctor_id}/schedule")
async def doctor_schedule(
    request: Request,
    doctor_id: int,
    date_str: str | None = None,
) -> list[dict[str, Any]]:
    target = date.fromisoformat(date_str) if date_str else date.today()
    engine = _availability(request)
    return engine.get_daily_schedule(_db(request), doctor_id, target)


# ── Availability ───────────────────────────────────────────────────────────


@router.get("/api/availability")
async def available_slots(
    request: Request,
    doctor_id: int,
    date_str: str,
    service_type: str | None = None,
) -> dict[str, Any]:
    target = date.fromisoformat(date_str)
    engine = _availability(request)
    slots = engine.get_available_slots(_db(request), doctor_id, target, service_type)
    return {"date": date_str, "doctor_id": doctor_id, "slots": slots}


# ── Appointments ───────────────────────────────────────────────────────────


@router.get("/api/appointments")
async def list_appointments(
    request: Request,
    date_str: str | None = None,
    doctor_id: int | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    conditions: list[str] = []
    params: list[Any] = []

    if date_str:
        conditions.append("a.appointment_date = ?")
        params.append(date_str)
    if doctor_id is not None:
        conditions.append("a.doctor_id = ?")
        params.append(doctor_id)
    if status:
        conditions.append("a.status = ?")
        params.append(status)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    with get_db(_db(request)) as conn:
        rows = conn.execute(
            f"""SELECT a.*, d.name_en AS doctor_name, d.name_tc AS doctor_name_tc
                FROM appointments a
                LEFT JOIN doctors d ON d.id = a.doctor_id
                {where}
                ORDER BY a.appointment_date, a.start_time""",  # noqa: S608
            params,
        ).fetchall()
    return [dict(r) for r in rows]


class CreateAppointmentRequest(BaseModel):
    patient_phone: str
    patient_name: str = ""
    patient_name_tc: str = ""
    doctor_id: int
    service_type: str = "gp"
    appointment_date: str
    start_time: str
    end_time: str
    room: str = ""
    source: str = "online"


@router.post("/api/appointments")
async def create_appointment(request: Request, body: CreateAppointmentRequest) -> dict[str, Any]:
    engine = _booking_engine()
    try:
        appt_id = engine.create_booking(_db(request), body.model_dump())
    except BookingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    reminder = _reminder(request)
    reminder.schedule_reminders(_db(request), appt_id, body.patient_phone)

    _availability(request).invalidate_cache(body.doctor_id)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="clinic-scheduler",
        summary=f"Appointment #{appt_id} booked for {body.patient_name or body.patient_phone} on {body.appointment_date}",
    )

    return {"appointment_id": appt_id, "status": "booked"}


class UpdateAppointmentRequest(BaseModel):
    status: str | None = None
    appointment_date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    doctor_id: int | None = None
    room: str | None = None
    version: int | None = None


@router.patch("/api/appointments/{appointment_id}")
async def update_appointment(
    request: Request,
    appointment_id: int,
    body: UpdateAppointmentRequest,
) -> dict[str, Any]:
    engine = _booking_engine()
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    try:
        updated = engine.update_booking(_db(request), appointment_id, **fields)
    except StaleVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _availability(request).invalidate_cache(updated.get("doctor_id"))

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="clinic-scheduler",
        summary=f"Appointment #{appointment_id} updated: {list(fields.keys())}",
    )

    return updated


@router.delete("/api/appointments/{appointment_id}")
async def cancel_appointment(request: Request, appointment_id: int) -> dict[str, Any]:
    db = _db(request)
    engine = _booking_engine()

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT doctor_id, appointment_date, patient_phone FROM appointments WHERE id = ?",
            (appointment_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appt_info = dict(row)

    try:
        success = engine.cancel_booking(db, appointment_id)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except StaleVersionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if not success:
        raise HTTPException(status_code=404, detail="Appointment not found")

    reminder = _reminder(request)
    reminder.cancel_reminders(appointment_id)

    _availability(request).invalidate_cache(appt_info["doctor_id"])

    wl = _waitlist_mgr()
    session = None
    matches = wl.match_cancellation(
        db,
        appt_info["doctor_id"],
        date.fromisoformat(appt_info["appointment_date"]),
        session,
    )
    for m in matches[:3]:
        wl.notify_available(db, m["id"])

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="clinic-scheduler",
        summary=f"Appointment #{appointment_id} cancelled",
    )

    return {"appointment_id": appointment_id, "status": "cancelled", "waitlist_notified": len(matches[:3])}


# ── Waitlist ───────────────────────────────────────────────────────────────


@router.get("/api/waitlist")
async def get_waitlist(
    request: Request,
    doctor_id: int | None = None,
    date_str: str | None = None,
) -> list[dict[str, Any]]:
    target = date.fromisoformat(date_str) if date_str else None
    mgr = _waitlist_mgr()
    return mgr.get_waitlist(_db(request), doctor_id=doctor_id, target_date=target)


class AddWaitlistRequest(BaseModel):
    patient_phone: str
    patient_name: str = ""
    doctor_id: int
    preferred_date: str
    preferred_session: str | None = None
    service_type: str | None = None
    priority: int = 0


@router.post("/api/waitlist")
async def add_to_waitlist(request: Request, body: AddWaitlistRequest) -> dict[str, Any]:
    mgr = _waitlist_mgr()
    try:
        wl_id = mgr.add_to_waitlist(_db(request), body.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    emit_event(
        _mona(request),
        event_type="info",
        tool_name="clinic-scheduler",
        summary=f"Waitlist #{wl_id}: {body.patient_name or body.patient_phone} for {body.preferred_date}",
    )

    return {"waitlist_id": wl_id, "status": "waiting"}


# ── Walk-in queue ──────────────────────────────────────────────────────────


@router.get("/api/walk-in/queue")
async def walk_in_queue(request: Request) -> list[dict[str, Any]]:
    wiq = _walk_in(request)
    return wiq.get_queue(_db(request))


class JoinWalkInRequest(BaseModel):
    patient_name: str
    patient_phone: str = ""
    service_type: str = "gp"


@router.post("/api/walk-in/join")
async def join_walk_in(request: Request, body: JoinWalkInRequest) -> dict[str, Any]:
    wiq = _walk_in(request)
    result = wiq.add_walk_in(_db(request), body.patient_name, body.patient_phone, body.service_type)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="clinic-scheduler",
        summary=f"Walk-in #{result['queue_number']}: {body.patient_name} ({body.service_type})",
    )

    return result


@router.post("/api/walk-in/next")
async def call_next_walk_in(request: Request) -> dict[str, Any]:
    wiq = _walk_in(request)
    entry = wiq.call_next(_db(request))
    if not entry:
        raise HTTPException(status_code=404, detail="No patients waiting")

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="clinic-scheduler",
        summary=f"Called walk-in #{entry['queue_number']}: {entry['patient_name']}",
    )

    return entry


@router.get("/api/walk-in/display")
async def walk_in_display(request: Request) -> dict[str, Any]:
    wiq = _walk_in(request)
    return wiq.get_display_data(_db(request))


# ── Today stats ────────────────────────────────────────────────────────────


@router.get("/api/today-stats")
async def today_stats(request: Request) -> dict[str, Any]:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        total = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE appointment_date = ?", (today,)
        ).fetchone()[0]
        completed = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE appointment_date = ? AND status = 'completed'",
            (today,),
        ).fetchone()[0]
        no_shows = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE appointment_date = ? AND status = 'no_show'",
            (today,),
        ).fetchone()[0]

    wiq = _walk_in(request)
    walk_in_data = wiq.get_display_data(db)
    walk_ins = walk_in_data["waiting_count"] + len(walk_in_data["currently_serving"])
    avg_wait = wiq.estimate_wait(db) // max(walk_in_data["waiting_count"], 1) if walk_in_data["waiting_count"] else 0

    return {
        "total": total,
        "completed": completed,
        "no_shows": no_shows,
        "walk_ins": walk_ins,
        "avg_wait": avg_wait,
    }


# ── WhatsApp Webhook ───────────────────────────────────────────────────────


@router.post("/api/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    form = await request.form()
    from_number = str(form.get("From", "")).replace("whatsapp:", "")
    message_body = str(form.get("Body", "")).strip()

    if not from_number or not message_body:
        raise HTTPException(status_code=400, detail="Missing From or Body")

    db = _db(request)
    engine = _availability(request)
    booking = _booking_engine()
    handler = WhatsAppBookingHandler(db, engine, booking)

    llm = request.app.state.llm
    response_text = await handler.handle_message(from_number, message_body, llm)

    emit_event(
        _mona(request),
        event_type="info",
        tool_name="clinic-scheduler",
        summary=f"WhatsApp from {from_number}: {message_body[:60]}",
    )

    return {"status": "processed", "response": response_text}
