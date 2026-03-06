"""WhatsApp message handler for clinic appointment booking via LLM intent extraction."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.llm.base import LLMProvider

from medical_dental.clinic_scheduler.bot.booking_flow import BookingFlow, FlowState
from medical_dental.clinic_scheduler.scheduling.availability import AvailabilityEngine
from medical_dental.clinic_scheduler.scheduling.booking_engine import BookingEngine

logger = logging.getLogger("openclaw.medical-dental.scheduler.whatsapp")

INTENT_SYSTEM_PROMPT = """\
You are an intent extraction assistant for a Hong Kong medical clinic's WhatsApp booking system.
Given the patient's message, extract:
- intent: one of "book", "cancel", "reschedule", "status", "unknown"
- entities: object with optional keys "doctor", "date", "time", "service_type"

Respond ONLY with valid JSON. Example:
{"intent": "book", "entities": {"doctor": "Ho", "date": "2026-03-10", "service_type": "gp"}}

If the message is a greeting or unclear, use intent "unknown" with empty entities.
"""

GREETING_RESPONSES: dict[str, str] = {
    "en": (
        "Hello! I'm the clinic assistant. I can help you:\n"
        "• Book an appointment\n"
        "• Cancel or reschedule\n"
        "• Check appointment status\n"
        "Just tell me what you need!"
    ),
    "tc": (
        "你好！我是診所助手，可以幫你：\n"
        "• 預約診症\n"
        "• 取消或更改預約\n"
        "• 查詢預約狀態\n"
        "請告訴我你的需要！"
    ),
}

_sessions: dict[str, BookingFlow] = {}


def _detect_language(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "tc"
    return "en"


def _get_session(phone: str, lang: str) -> BookingFlow:
    if phone not in _sessions:
        _sessions[phone] = BookingFlow(language=lang)
    session = _sessions[phone]
    session.language = lang
    return session


class WhatsAppBookingHandler:
    """Processes incoming WhatsApp messages for appointment booking."""

    def __init__(
        self,
        db_path: str | Path,
        availability: AvailabilityEngine,
        booking: BookingEngine,
    ) -> None:
        self._db_path = str(db_path)
        self._availability = availability
        self._booking = booking

    async def handle_message(
        self,
        from_phone: str,
        message_text: str,
        llm_provider: LLMProvider,
    ) -> str:
        lang = _detect_language(message_text)
        session = _get_session(from_phone, lang)

        if session.state != FlowState.INIT and session.state != FlowState.DONE:
            return self._continue_flow(session, from_phone, message_text)

        parsed = await self._extract_intent(message_text, llm_provider)
        intent = parsed.get("intent", "unknown")
        entities = parsed.get("entities", {})

        if intent == "book":
            return await self._start_booking(session, from_phone, entities)
        if intent == "cancel":
            return self._handle_cancel(from_phone, lang)
        if intent == "reschedule":
            return self._handle_reschedule(from_phone, lang)
        if intent == "status":
            return self._handle_status(from_phone, lang)

        return GREETING_RESPONSES.get(lang, GREETING_RESPONSES["en"])

    async def _extract_intent(self, text: str, llm: LLMProvider) -> dict[str, Any]:
        try:
            raw = await llm.generate(
                text,
                system=INTENT_SYSTEM_PROMPT,
                max_tokens=256,
                temperature=0.1,
            )
            raw = raw.strip()
            start = raw.find("{")
            end = raw.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw[start:end])
        except Exception:
            logger.exception("LLM intent extraction failed for: %s", text[:100])
        return {"intent": "unknown", "entities": {}}

    async def _start_booking(
        self,
        session: BookingFlow,
        phone: str,
        entities: dict[str, Any],
    ) -> str:
        session.reset()
        lang = session.language

        from openclaw_shared.database import get_db
        with get_db(self._db_path) as conn:
            doctors = [dict(r) for r in conn.execute(
                "SELECT id, name_en, name_tc, specialty FROM doctors WHERE active = 1"
            ).fetchall()]

        session.set_doctors(doctors)

        if entities.get("doctor"):
            matched = self._match_doctor(doctors, entities["doctor"])
            if matched:
                session.collected["doctor_id"] = matched["id"]
                session.collected["doctor_name"] = matched.get("name_en", "")
                session.state = FlowState.SELECT_SERVICE
                return session.advance("")

        session.state = FlowState.INIT
        return session.advance("book")

    def _continue_flow(self, session: BookingFlow, phone: str, text: str) -> str:
        if session.state == FlowState.SELECT_DATE:
            response = session.advance(text)
            if session.state == FlowState.SELECT_TIME:
                doctor_id = session.collected.get("doctor_id")
                date_str = session.collected.get("appointment_date")
                service = session.collected.get("service_type")
                if doctor_id and date_str:
                    slots = self._availability.get_available_slots(
                        self._db_path,
                        doctor_id,
                        date.fromisoformat(date_str),
                        service,
                    )
                    session.set_available_slots(slots)
                    return session._time_prompt(session.language)
            return response

        if session.state == FlowState.CONFIRM:
            response = session.advance(text)
            if session.state == FlowState.DONE:
                try:
                    appt_id = self._booking.create_booking(self._db_path, {
                        "patient_phone": phone,
                        "doctor_id": session.collected["doctor_id"],
                        "appointment_date": session.collected["appointment_date"],
                        "start_time": session.collected["start_time"],
                        "end_time": session.collected["end_time"],
                        "room": session.collected.get("room", ""),
                        "service_type": session.collected.get("service_type", "gp"),
                        "source": "whatsapp",
                    })
                    session.set_appointment_id(appt_id)
                    from medical_dental.clinic_scheduler.bot.booking_flow import PROMPTS
                    return PROMPTS[FlowState.DONE][session.language].format(appt_id=appt_id)
                except Exception:
                    logger.exception("Booking creation failed for %s", phone)
                    error = {
                        "en": "Sorry, there was an error creating your booking. Please try again.",
                        "tc": "抱歉，預約時發生錯誤，請重試。",
                    }
                    session.reset()
                    return error[session.language]
            return response

        return session.advance(text)

    def _handle_cancel(self, phone: str, lang: str) -> str:
        from openclaw_shared.database import get_db
        with get_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT id, appointment_date, start_time, doctor_id
                   FROM appointments
                   WHERE patient_phone = ? AND status IN ('booked', 'confirmed')
                   ORDER BY appointment_date, start_time""",
                (phone,),
            ).fetchall()

        if not rows:
            return {
                "en": "You don't have any upcoming appointments to cancel.",
                "tc": "你沒有可取消的預約。",
            }[lang]

        appts = [dict(r) for r in rows]
        if len(appts) == 1:
            self._booking.cancel_booking(self._db_path, appts[0]["id"])
            return {
                "en": f"Your appointment on {appts[0]['appointment_date']} at {appts[0]['start_time']} has been cancelled.",
                "tc": f"你在 {appts[0]['appointment_date']} {appts[0]['start_time']} 的預約已取消。",
            }[lang]

        lines = [f"{i + 1}. {a['appointment_date']} {a['start_time']}" for i, a in enumerate(appts)]
        return {
            "en": "Which appointment to cancel?\n" + "\n".join(lines) + "\nReply with the number.",
            "tc": "取消哪個預約？\n" + "\n".join(lines) + "\n輸入數字選擇。",
        }[lang]

    def _handle_reschedule(self, phone: str, lang: str) -> str:
        return {
            "en": "To reschedule, please cancel your current appointment and book a new one. Type 'cancel' to start.",
            "tc": "如需改期，請先取消現有預約再重新預約。輸入「取消」開始。",
        }[lang]

    def _handle_status(self, phone: str, lang: str) -> str:
        from openclaw_shared.database import get_db
        with get_db(self._db_path) as conn:
            rows = conn.execute(
                """SELECT a.appointment_date, a.start_time, a.end_time, a.status,
                          a.service_type, d.name_en, d.name_tc
                   FROM appointments a
                   LEFT JOIN doctors d ON d.id = a.doctor_id
                   WHERE a.patient_phone = ? AND a.status NOT IN ('cancelled', 'completed', 'no_show')
                   ORDER BY a.appointment_date, a.start_time""",
                (phone,),
            ).fetchall()

        if not rows:
            return {
                "en": "You don't have any upcoming appointments.",
                "tc": "你目前沒有預約。",
            }[lang]

        parts: list[str] = []
        for r in rows:
            row_d = dict(r)
            doc = row_d.get("name_tc" if lang == "tc" else "name_en", "")
            parts.append(
                f"• {row_d['appointment_date']} {row_d['start_time']} - {doc} ({row_d['status']})"
            )

        header = {"en": "Your upcoming appointments:", "tc": "你的預約："}[lang]
        return header + "\n" + "\n".join(parts)

    @staticmethod
    def _match_doctor(doctors: list[dict[str, Any]], name_fragment: str) -> dict[str, Any] | None:
        fragment_lower = name_fragment.lower()
        for doc in doctors:
            if fragment_lower in doc.get("name_en", "").lower():
                return doc
            if name_fragment in doc.get("name_tc", ""):
                return doc
        return None
