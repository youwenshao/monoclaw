"""Appointment reminder scheduler using APScheduler."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db
from openclaw_shared.messaging.base import MessagingProvider

logger = logging.getLogger("openclaw.medical-dental.scheduler.reminders")

REMINDER_24H_EN = (
    "Reminder: You have an appointment tomorrow ({date}) at {time} "
    "with {doctor}. Please reply CONFIRM to confirm or CANCEL to cancel."
)
REMINDER_24H_TC = (
    "提醒：你明天（{date}）{time} 有預約，"
    "醫生：{doctor}。回覆「確認」確認出席或「取消」取消預約。"
)
REMINDER_2H_EN = (
    "Your appointment is in 2 hours at {time} with {doctor}. "
    "Please arrive 10 minutes early. Address: {address}"
)
REMINDER_2H_TC = (
    "你的預約將在2小時後（{time}）開始，醫生：{doctor}。"
    "請提早10分鐘到達。地址：{address}"
)


def _job_id(appointment_id: int, kind: str) -> str:
    return f"reminder_{appointment_id}_{kind}"


def _get_appointment(db_path: str | Path, appointment_id: int) -> dict[str, Any] | None:
    with get_db(db_path) as conn:
        row = conn.execute(
            """SELECT a.*, d.name_en AS doctor_name, d.name_tc AS doctor_name_tc
               FROM appointments a
               LEFT JOIN doctors d ON d.id = a.doctor_id
               WHERE a.id = ?""",
            (appointment_id,),
        ).fetchone()
    return dict(row) if row else None


class ReminderSender:
    """Schedules and sends appointment reminders via WhatsApp/SMS."""

    def __init__(
        self,
        messaging: MessagingProvider | None = None,
        clinic_address: str = "",
        default_language: str = "en",
    ) -> None:
        self._messaging = messaging
        self._clinic_address = clinic_address
        self._default_language = default_language
        self._scheduler: Any = None

    def _get_scheduler(self) -> Any:
        if self._scheduler is None:
            from apscheduler.schedulers.asyncio import AsyncIOScheduler
            self._scheduler = AsyncIOScheduler()
            self._scheduler.start()
        return self._scheduler

    def schedule_reminders(
        self,
        db_path: str | Path,
        appointment_id: int,
        patient_phone: str,
    ) -> None:
        appt = _get_appointment(db_path, appointment_id)
        if not appt:
            logger.warning("Appointment #%d not found for reminder scheduling", appointment_id)
            return

        appt_dt = datetime.fromisoformat(f"{appt['appointment_date']}T{appt['start_time']}")

        reminder_24h = appt_dt - timedelta(hours=24)
        reminder_2h = appt_dt - timedelta(hours=2)
        now = datetime.now()

        scheduler = self._get_scheduler()

        if reminder_24h > now:
            scheduler.add_job(
                self._send_24h_wrapper,
                "date",
                run_date=reminder_24h,
                id=_job_id(appointment_id, "24h"),
                replace_existing=True,
                kwargs={"db_path": str(db_path), "appointment_id": appointment_id},
            )
            logger.info("Scheduled 24h reminder for appt #%d at %s", appointment_id, reminder_24h)

        if reminder_2h > now:
            scheduler.add_job(
                self._send_2h_wrapper,
                "date",
                run_date=reminder_2h,
                id=_job_id(appointment_id, "2h"),
                replace_existing=True,
                kwargs={"db_path": str(db_path), "appointment_id": appointment_id},
            )
            logger.info("Scheduled 2h reminder for appt #%d at %s", appointment_id, reminder_2h)

    async def send_24h_reminder(self, appointment: dict[str, Any]) -> bool:
        if appointment.get("status") in ("cancelled", "no_show"):
            return False

        lang = self._default_language
        doctor = appointment.get("doctor_name_tc" if lang == "tc" else "doctor_name", "")
        template = REMINDER_24H_TC if lang == "tc" else REMINDER_24H_EN
        text = template.format(
            date=appointment["appointment_date"],
            time=appointment["start_time"],
            doctor=doctor,
        )

        return await self._send(appointment["patient_phone"], text)

    async def send_2h_reminder(self, appointment: dict[str, Any]) -> bool:
        if appointment.get("status") in ("cancelled", "no_show"):
            return False

        lang = self._default_language
        doctor = appointment.get("doctor_name_tc" if lang == "tc" else "doctor_name", "")
        template = REMINDER_2H_TC if lang == "tc" else REMINDER_2H_EN
        text = template.format(
            time=appointment["start_time"],
            doctor=doctor,
            address=self._clinic_address or "N/A",
        )

        return await self._send(appointment["patient_phone"], text)

    def cancel_reminders(self, appointment_id: int) -> None:
        scheduler = self._get_scheduler()
        for kind in ("24h", "2h"):
            job_id = _job_id(appointment_id, kind)
            try:
                scheduler.remove_job(job_id)
                logger.info("Cancelled reminder job %s", job_id)
            except Exception:
                pass

    async def _send(self, phone: str, text: str) -> bool:
        if not self._messaging:
            logger.info("Messaging not configured — reminder text: %s", text[:80])
            return False
        try:
            await self._messaging.send_text(phone, text)
            return True
        except Exception:
            logger.exception("Failed to send reminder to %s", phone)
            return False

    async def _send_24h_wrapper(self, db_path: str, appointment_id: int) -> None:
        appt = _get_appointment(db_path, appointment_id)
        if appt:
            await self.send_24h_reminder(appt)
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE appointments SET reminder_sent = 1 WHERE id = ?",
                    (appointment_id,),
                )

    async def _send_2h_wrapper(self, db_path: str, appointment_id: int) -> None:
        appt = _get_appointment(db_path, appointment_id)
        if appt:
            await self.send_2h_reminder(appt)
