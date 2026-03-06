"""Booking engine with optimistic locking for the ClinicScheduler."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.scheduler.booking")

VALID_STATUSES = frozenset({
    "booked", "confirmed", "arrived", "in_progress", "completed", "cancelled", "no_show",
})

ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    "booked": frozenset({"confirmed", "cancelled"}),
    "confirmed": frozenset({"arrived", "cancelled", "no_show"}),
    "arrived": frozenset({"in_progress"}),
    "in_progress": frozenset({"completed"}),
}


class BookingConflictError(Exception):
    pass


class StaleVersionError(Exception):
    pass


class InvalidTransitionError(Exception):
    pass


class BookingEngine:
    """CRUD operations on appointments with optimistic-locking version checks."""

    def create_booking(self, db_path: str | Path, data: dict[str, Any]) -> int:
        required = ("patient_phone", "doctor_id", "appointment_date", "start_time", "end_time")
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        with get_db(db_path) as conn:
            conflict = conn.execute(
                """SELECT id FROM appointments
                   WHERE doctor_id = ? AND appointment_date = ? AND status != 'cancelled'
                     AND start_time < ? AND end_time > ?""",
                (data["doctor_id"], data["appointment_date"], data["end_time"], data["start_time"]),
            ).fetchone()
            if conflict:
                raise BookingConflictError(
                    f"Time slot conflicts with existing appointment #{conflict['id']}"
                )

            cursor = conn.execute(
                """INSERT INTO appointments
                   (patient_phone, patient_name, patient_name_tc, doctor_id, service_type,
                    appointment_date, start_time, end_time, room, status, source, version)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,1)""",
                (
                    data["patient_phone"],
                    data.get("patient_name", ""),
                    data.get("patient_name_tc", ""),
                    data["doctor_id"],
                    data.get("service_type", "gp"),
                    data["appointment_date"],
                    data["start_time"],
                    data["end_time"],
                    data.get("room", ""),
                    "booked",
                    data.get("source", "whatsapp"),
                ),
            )
            appointment_id: int = cursor.lastrowid  # type: ignore[assignment]

        logger.info(
            "Created appointment #%d for %s with doctor %s on %s",
            appointment_id, data["patient_phone"], data["doctor_id"], data["appointment_date"],
        )
        return appointment_id

    def update_booking(
        self,
        db_path: str | Path,
        appointment_id: int,
        **fields: Any,
    ) -> dict[str, Any]:
        if not fields:
            raise ValueError("No fields to update")

        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
            ).fetchone()
            if not row:
                raise ValueError(f"Appointment #{appointment_id} not found")

            current = dict(row)
            current_version = current["version"]

            if "status" in fields:
                new_status = fields["status"]
                self._validate_transition(current["status"], new_status)

            expected_version = fields.pop("version", current_version)
            if expected_version != current_version:
                raise StaleVersionError(
                    f"Version mismatch: expected {expected_version}, got {current_version}"
                )

            if "doctor_id" in fields or "start_time" in fields or "end_time" in fields or "appointment_date" in fields:
                check_doctor = fields.get("doctor_id", current["doctor_id"])
                check_date = fields.get("appointment_date", current["appointment_date"])
                check_start = fields.get("start_time", current["start_time"])
                check_end = fields.get("end_time", current["end_time"])

                conflict = conn.execute(
                    """SELECT id FROM appointments
                       WHERE doctor_id = ? AND appointment_date = ? AND id != ?
                         AND status != 'cancelled'
                         AND start_time < ? AND end_time > ?""",
                    (check_doctor, check_date, appointment_id, check_end, check_start),
                ).fetchone()
                if conflict:
                    raise BookingConflictError(
                        f"Reschedule conflicts with appointment #{conflict['id']}"
                    )

            updatable = {
                "patient_name", "patient_name_tc", "doctor_id", "service_type",
                "appointment_date", "start_time", "end_time", "room",
                "status", "reminder_sent", "source",
            }
            to_set = {k: v for k, v in fields.items() if k in updatable}
            if not to_set:
                raise ValueError("No valid fields to update")

            to_set["version"] = current_version + 1
            set_clause = ", ".join(f"{k} = ?" for k in to_set)
            values = list(to_set.values()) + [appointment_id, current_version]

            result = conn.execute(
                f"UPDATE appointments SET {set_clause} WHERE id = ? AND version = ?",  # noqa: S608
                values,
            )
            if result.rowcount == 0:
                raise StaleVersionError("Concurrent modification detected")

            updated = conn.execute(
                "SELECT * FROM appointments WHERE id = ?", (appointment_id,)
            ).fetchone()

        logger.info("Updated appointment #%d: %s", appointment_id, to_set)
        return dict(updated)

    def cancel_booking(self, db_path: str | Path, appointment_id: int) -> bool:
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT status, version FROM appointments WHERE id = ?", (appointment_id,)
            ).fetchone()
            if not row:
                return False

            current_status = row["status"]
            if current_status == "cancelled":
                return True
            if current_status not in ("booked", "confirmed"):
                raise InvalidTransitionError(
                    f"Cannot cancel appointment in '{current_status}' state"
                )

            result = conn.execute(
                """UPDATE appointments
                   SET status = 'cancelled', version = version + 1
                   WHERE id = ? AND version = ?""",
                (appointment_id, row["version"]),
            )
            if result.rowcount == 0:
                raise StaleVersionError("Concurrent modification detected")

        logger.info("Cancelled appointment #%d", appointment_id)
        return True

    def get_today_appointments(self, db_path: str | Path) -> list[dict[str, Any]]:
        today = date.today().isoformat()
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT a.*, d.name_en AS doctor_name, d.name_tc AS doctor_name_tc
                   FROM appointments a
                   LEFT JOIN doctors d ON d.id = a.doctor_id
                   WHERE a.appointment_date = ?
                   ORDER BY a.start_time""",
                (today,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_doctor_appointments(
        self,
        db_path: str | Path,
        doctor_id: int,
        target_date: date,
    ) -> list[dict[str, Any]]:
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM appointments
                   WHERE doctor_id = ? AND appointment_date = ?
                   ORDER BY start_time""",
                (doctor_id, target_date.isoformat()),
            ).fetchall()
        return [dict(r) for r in rows]

    @staticmethod
    def _validate_transition(current: str, new: str) -> None:
        if new not in VALID_STATUSES:
            raise InvalidTransitionError(f"Invalid status: {new}")
        allowed = ALLOWED_TRANSITIONS.get(current, frozenset())
        if new not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from '{current}' to '{new}'"
            )
