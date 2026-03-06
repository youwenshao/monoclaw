"""APScheduler-based reminder scheduler for medication time slots."""

from __future__ import annotations

import json
import logging
from datetime import datetime, time
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.scheduler")


def _ensure_apscheduler() -> Any:
    """Import APScheduler with a graceful fallback."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
        from apscheduler.triggers.cron import CronTrigger
        return BackgroundScheduler, SQLAlchemyJobStore, CronTrigger
    except ImportError:
        return None, None, None


class ReminderScheduler:
    """Wrap APScheduler to manage per-patient, per-medication cron jobs."""

    def __init__(self, job_store_path: str | Path | None = None) -> None:
        BackgroundScheduler, SQLAlchemyJobStore, CronTrigger = _ensure_apscheduler()

        self._has_apscheduler = BackgroundScheduler is not None
        self._scheduler: Any | None = None
        self._CronTrigger = CronTrigger

        if self._has_apscheduler and job_store_path:
            store_url = f"sqlite:///{job_store_path}"
            jobstores = {"default": SQLAlchemyJobStore(url=store_url)}
            self._scheduler = BackgroundScheduler(jobstores=jobstores)
            self._scheduler.start(paused=False)
        elif self._has_apscheduler:
            self._scheduler = BackgroundScheduler()
            self._scheduler.start(paused=False)
        else:
            logger.warning("APScheduler not installed — scheduler running in no-op mode")

        self._jobs: dict[str, dict] = {}

    def schedule_patient_reminders(
        self,
        db_path: str | Path,
        patient_id: int,
    ) -> list[str]:
        """Create reminder jobs for all active medications of a patient.

        Returns list of job IDs created.
        """
        created_ids: list[str] = []

        with get_db(db_path) as conn:
            meds = conn.execute(
                "SELECT * FROM medications WHERE patient_id = ? AND active = 1",
                (patient_id,),
            ).fetchall()

        for med in meds:
            med_dict = dict(med)
            time_slots = _parse_time_slots(med_dict.get("time_slots", "[]"))
            for slot in time_slots:
                job_id = f"remind_{patient_id}_{med_dict['id']}_{slot}"
                self._add_job(job_id, slot, db_path, patient_id, med_dict["id"])
                created_ids.append(job_id)

        logger.info(
            "Scheduled %d reminder jobs for patient %d", len(created_ids), patient_id
        )
        return created_ids

    def cancel_patient_reminders(self, patient_id: int) -> int:
        """Remove all scheduled jobs for a patient. Returns count removed."""
        prefix = f"remind_{patient_id}_"
        removed = 0

        to_remove = [jid for jid in self._jobs if jid.startswith(prefix)]
        for jid in to_remove:
            self._remove_job(jid)
            removed += 1

        logger.info("Cancelled %d reminder jobs for patient %d", removed, patient_id)
        return removed

    def reschedule_medication(
        self,
        patient_id: int,
        medication_id: int,
        new_times: list[str],
    ) -> list[str]:
        """Replace scheduled times for a specific medication.

        Returns the new job IDs.
        """
        prefix = f"remind_{patient_id}_{medication_id}_"
        for jid in list(self._jobs):
            if jid.startswith(prefix):
                self._remove_job(jid)

        new_ids: list[str] = []
        for slot in new_times:
            job_id = f"remind_{patient_id}_{medication_id}_{slot}"
            self._add_job(job_id, slot, "", patient_id, medication_id)
            new_ids.append(job_id)

        return new_ids

    def get_scheduled_jobs(self, patient_id: int | None = None) -> list[dict]:
        """Return metadata about scheduled jobs, optionally filtered by patient."""
        results: list[dict] = []
        for jid, meta in self._jobs.items():
            if patient_id is not None and meta.get("patient_id") != patient_id:
                continue
            results.append({"job_id": jid, **meta})
        return results

    def shutdown(self) -> None:
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)

    # ------------------------------------------------------------------

    def _add_job(
        self,
        job_id: str,
        time_slot: str,
        db_path: str | Path,
        patient_id: int,
        medication_id: int,
    ) -> None:
        hour, minute = _parse_hhmm(time_slot)
        meta = {
            "patient_id": patient_id,
            "medication_id": medication_id,
            "time_slot": time_slot,
            "hour": hour,
            "minute": minute,
        }

        if self._scheduler is not None and self._CronTrigger is not None:
            trigger = self._CronTrigger(hour=hour, minute=minute)
            self._scheduler.add_job(
                _reminder_callback,
                trigger=trigger,
                id=job_id,
                replace_existing=True,
                kwargs={
                    "db_path": str(db_path),
                    "patient_id": patient_id,
                    "medication_id": medication_id,
                },
            )

        self._jobs[job_id] = meta

    def _remove_job(self, job_id: str) -> None:
        if self._scheduler is not None:
            try:
                self._scheduler.remove_job(job_id)
            except Exception:
                pass
        self._jobs.pop(job_id, None)


def _reminder_callback(
    db_path: str,
    patient_id: int,
    medication_id: int,
) -> None:
    """Callback invoked by APScheduler when a reminder fires.

    Inserts a compliance_log row so the system knows a reminder was sent.
    """
    now = datetime.now().isoformat()
    try:
        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO compliance_logs
                   (patient_id, medication_id, reminder_sent_at)
                   VALUES (?, ?, ?)""",
                (patient_id, medication_id, now),
            )
        logger.info(
            "Reminder fired: patient=%d med=%d at %s", patient_id, medication_id, now
        )
    except Exception:
        logger.exception("Failed to record reminder for patient %d", patient_id)


def _parse_time_slots(raw: str) -> list[str]:
    """Parse a JSON list of HH:MM strings."""
    try:
        slots = json.loads(raw)
        if isinstance(slots, list):
            return [str(s).strip() for s in slots if s]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def _parse_hhmm(slot: str) -> tuple[int, int]:
    """Convert 'HH:MM' to (hour, minute) with defaults."""
    try:
        parts = slot.split(":")
        return int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        return 8, 0
