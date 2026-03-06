"""MedReminder FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from medical_dental.med_reminder.bot.whatsapp_handler import MedReminderWhatsAppHandler
from medical_dental.med_reminder.reminders.compliance_tracker import ComplianceTracker
from medical_dental.med_reminder.reminders.escalation import EscalationManager
from medical_dental.med_reminder.refill.refill_workflow import RefillWorkflow
from medical_dental.med_reminder.safety.interaction_checker import InteractionChecker

router = APIRouter(prefix="/med-reminder", tags=["MedReminder"])

templates = Jinja2Templates(directory="medical_dental/dashboard/templates")

_compliance = ComplianceTracker()
_escalation = EscalationManager()
_refill = RefillWorkflow()
_interactions = InteractionChecker()


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "med-reminder", **extra}


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["med_reminder"])


# ── Page ───────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def med_reminder_page(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        patient_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
        active_meds = conn.execute(
            "SELECT COUNT(*) FROM medications WHERE active = 1"
        ).fetchone()[0]
        pending_refills = conn.execute(
            "SELECT COUNT(*) FROM refill_requests WHERE status = 'pending'"
        ).fetchone()[0]
        today_reminders = conn.execute(
            """SELECT COUNT(*) FROM compliance_logs
               WHERE DATE(reminder_sent_at) = ?""",
            (today,),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "med_reminder/index.html",
        _ctx(
            request,
            patient_count=patient_count,
            active_meds=active_meds,
            pending_refills=pending_refills,
            today_reminders=today_reminders,
        ),
    )


# ── Patients ───────────────────────────────────────────────────────────────


@router.get("/api/patients")
async def list_patients(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        patients = [dict(r) for r in conn.execute(
            "SELECT * FROM patients ORDER BY name_en"
        ).fetchall()]

    for p in patients:
        compliance = _compliance.get_patient_compliance(db, p["id"], days=30)
        p["compliance_rate"] = compliance["overall_rate"]

    return patients


@router.get("/api/patients/{patient_id}/medications")
async def patient_medications(request: Request, patient_id: int) -> list[dict[str, Any]]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")

    with get_db(db) as conn:
        meds = [dict(r) for r in conn.execute(
            "SELECT * FROM medications WHERE patient_id = ? AND active = 1 ORDER BY drug_name_en",
            (patient_id,),
        ).fetchall()]
    return meds


class AddMedicationRequest(BaseModel):
    drug_name_en: str
    drug_name_tc: str | None = None
    dosage: str
    frequency: str
    time_slots: list[str] | None = None
    prescribing_doctor: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    refill_eligible: bool = True


@router.post("/api/patients/{patient_id}/medications")
async def add_medication(request: Request, patient_id: int, body: AddMedicationRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM patients WHERE id = ?", (patient_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Patient not found")

    time_slots_json = json.dumps(body.time_slots) if body.time_slots else "[]"
    start = body.start_date or date.today().isoformat()

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO medications
               (patient_id, drug_name_en, drug_name_tc, dosage, frequency,
                time_slots, prescribing_doctor, start_date, end_date, refill_eligible, active)
               VALUES (?,?,?,?,?,?,?,?,?,?,1)""",
            (patient_id, body.drug_name_en, body.drug_name_tc, body.dosage,
             body.frequency, time_slots_json, body.prescribing_doctor, start,
             body.end_date, body.refill_eligible),
        )
        med_id = cursor.lastrowid

    interactions = _interactions.check_interactions(db, patient_id, new_drug=body.drug_name_en)
    if interactions:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="alert",
            tool_name="med-reminder",
            summary=f"Drug interaction detected for patient #{patient_id}: {body.drug_name_en}",
            details=json.dumps(interactions, ensure_ascii=False),
            requires_human_action=True,
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="med-reminder",
        summary=f"Medication {body.drug_name_en} added for patient #{patient_id}",
    )

    return {"medication_id": med_id, "interactions": interactions}


# ── Reminders ──────────────────────────────────────────────────────────────


@router.get("/api/reminders/today")
async def todays_reminders(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT cl.*, p.name_en, p.name_tc, p.phone,
                      m.drug_name_en, m.drug_name_tc, m.dosage
               FROM compliance_logs cl
               LEFT JOIN patients p ON p.id = cl.patient_id
               LEFT JOIN medications m ON m.id = cl.medication_id
               WHERE DATE(cl.reminder_sent_at) = ?
               ORDER BY cl.reminder_sent_at DESC""",
            (today,),
        ).fetchall()

    return [dict(r) for r in rows]


@router.post("/api/reminders/{patient_id}/{med_id}/taken")
async def mark_taken(request: Request, patient_id: int, med_id: int) -> dict[str, Any]:
    db = _db(request)
    log_id = _compliance.record_taken(db, patient_id, med_id)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="med-reminder",
        summary=f"Patient #{patient_id} confirmed medication #{med_id} taken",
    )

    return {"log_id": log_id, "status": "taken"}


# ── Compliance ─────────────────────────────────────────────────────────────


@router.get("/api/compliance/{patient_id}")
async def compliance_report(request: Request, patient_id: int, days: int = 30) -> dict[str, Any]:
    db = _db(request)
    return _compliance.get_patient_compliance(db, patient_id, days=days)


@router.get("/api/compliance/low")
async def low_compliance(request: Request, threshold: float = 60) -> list[dict[str, Any]]:
    db = _db(request)
    return _compliance.get_low_compliance_patients(db, threshold=threshold)


# ── Refills ────────────────────────────────────────────────────────────────


@router.get("/api/refills")
async def pending_refills(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    return _refill.get_pending_requests(db)


class CreateRefillRequest(BaseModel):
    patient_id: int
    medication_id: int
    photo_path: str | None = None
    ocr_result: str | None = None


@router.post("/api/refills")
async def create_refill(request: Request, body: CreateRefillRequest) -> dict[str, Any]:
    db = _db(request)
    request_id = _refill.create_request(
        db, body.patient_id, body.medication_id, body.photo_path, body.ocr_result,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="approval_needed",
        tool_name="med-reminder",
        summary=f"Refill request #{request_id} for patient #{body.patient_id}",
        requires_human_action=True,
    )

    return {"request_id": request_id, "status": "pending"}


class UpdateRefillRequest(BaseModel):
    action: str
    reviewed_by: str | None = None
    reason: str | None = None
    notes: str | None = None


@router.patch("/api/refills/{request_id}")
async def update_refill(request: Request, request_id: int, body: UpdateRefillRequest) -> dict[str, Any]:
    db = _db(request)
    reviewer = body.reviewed_by or "system"
    success = False

    if body.action == "approve":
        success = _refill.approve_request(db, request_id, reviewer, body.notes)
    elif body.action == "reject":
        success = _refill.reject_request(db, request_id, reviewer, body.reason or "")
    elif body.action == "ready":
        success = _refill.mark_ready(db, request_id)
    elif body.action == "collected":
        success = _refill.mark_collected(db, request_id)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {body.action}")

    if not success:
        raise HTTPException(status_code=409, detail="Transition not allowed or request not found")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="med-reminder",
        summary=f"Refill #{request_id} updated: {body.action}",
    )

    return {"request_id": request_id, "action": body.action, "success": True}


# ── Interactions ───────────────────────────────────────────────────────────


@router.get("/api/interactions/{patient_id}")
async def patient_interactions(request: Request, patient_id: int) -> list[dict[str, Any]]:
    db = _db(request)
    return _interactions.check_interactions(db, patient_id)


class CheckInteractionRequest(BaseModel):
    drug_a: str
    drug_b: str


@router.post("/api/interactions/check")
async def check_interaction(request: Request, body: CheckInteractionRequest) -> dict[str, Any]:
    db = _db(request)
    result = _interactions.check_pair(db, body.drug_a, body.drug_b)
    if result is None:
        return {"interaction": False, "drug_a": body.drug_a, "drug_b": body.drug_b}
    return {"interaction": True, **result}


# ── WhatsApp Webhook ───────────────────────────────────────────────────────


@router.post("/api/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    form = await request.form()
    from_number = str(form.get("From", ""))
    message_body = str(form.get("Body", ""))
    media_url = str(form.get("MediaUrl0", "")) or None

    db = _db(request)
    handler = MedReminderWhatsAppHandler(db, llm=request.app.state.llm)
    response = handler.handle_message(from_number, message_body, media_url=media_url)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="info",
        tool_name="med-reminder",
        summary=f"WhatsApp message from {from_number}: {message_body[:60]}",
    )

    return {"status": "processed", "response": response}
