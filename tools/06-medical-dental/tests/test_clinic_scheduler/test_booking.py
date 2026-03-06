"""Tests for the booking engine with optimistic locking."""

from datetime import date, timedelta

import pytest

from openclaw_shared.database import get_db
from medical_dental.clinic_scheduler.scheduling.booking_engine import (
    BookingConflictError,
    BookingEngine,
    InvalidTransitionError,
    StaleVersionError,
)


def _setup_doctor(db_path):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO doctors (name_en, specialty, default_slot_duration, active) VALUES (?, ?, ?, ?)",
            ("Dr. Booking", "GP", 15, True),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _future_date():
    return (date.today() + timedelta(days=7)).isoformat()


def test_create_booking(db_paths):
    db = db_paths["clinic_scheduler"]
    engine = BookingEngine()
    doctor_id = _setup_doctor(db)

    appt_id = engine.create_booking(db, {
        "patient_phone": "+85291111111",
        "patient_name": "Test Booker",
        "doctor_id": doctor_id,
        "appointment_date": _future_date(),
        "start_time": "10:00",
        "end_time": "10:15",
        "service_type": "gp",
    })
    assert appt_id > 0

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    assert row is not None
    assert row["status"] == "booked"
    assert row["version"] == 1
    assert row["patient_phone"] == "+85291111111"


def test_double_booking_prevented(db_paths):
    db = db_paths["clinic_scheduler"]
    engine = BookingEngine()
    doctor_id = _setup_doctor(db)
    appt_date = _future_date()

    engine.create_booking(db, {
        "patient_phone": "+85291111112",
        "doctor_id": doctor_id,
        "appointment_date": appt_date,
        "start_time": "11:00",
        "end_time": "11:15",
    })

    with pytest.raises(BookingConflictError):
        engine.create_booking(db, {
            "patient_phone": "+85291111113",
            "doctor_id": doctor_id,
            "appointment_date": appt_date,
            "start_time": "11:00",
            "end_time": "11:15",
        })


def test_status_transitions(db_paths):
    db = db_paths["clinic_scheduler"]
    engine = BookingEngine()
    doctor_id = _setup_doctor(db)

    appt_id = engine.create_booking(db, {
        "patient_phone": "+85291111114",
        "doctor_id": doctor_id,
        "appointment_date": _future_date(),
        "start_time": "14:00",
        "end_time": "14:15",
    })

    result = engine.update_booking(db, appt_id, status="confirmed")
    assert result["status"] == "confirmed"

    result = engine.update_booking(db, appt_id, status="arrived")
    assert result["status"] == "arrived"

    result = engine.update_booking(db, appt_id, status="in_progress")
    assert result["status"] == "in_progress"

    result = engine.update_booking(db, appt_id, status="completed")
    assert result["status"] == "completed"


def test_cancel_booking(db_paths):
    db = db_paths["clinic_scheduler"]
    engine = BookingEngine()
    doctor_id = _setup_doctor(db)

    appt_id = engine.create_booking(db, {
        "patient_phone": "+85291111115",
        "doctor_id": doctor_id,
        "appointment_date": _future_date(),
        "start_time": "15:00",
        "end_time": "15:15",
    })

    assert engine.cancel_booking(db, appt_id) is True

    with get_db(db) as conn:
        row = conn.execute("SELECT status FROM appointments WHERE id = ?", (appt_id,)).fetchone()
    assert row["status"] == "cancelled"


def test_optimistic_lock_stale(db_paths):
    db = db_paths["clinic_scheduler"]
    engine = BookingEngine()
    doctor_id = _setup_doctor(db)

    appt_id = engine.create_booking(db, {
        "patient_phone": "+85291111116",
        "doctor_id": doctor_id,
        "appointment_date": _future_date(),
        "start_time": "16:00",
        "end_time": "16:15",
    })

    with pytest.raises(StaleVersionError):
        engine.update_booking(db, appt_id, status="confirmed", version=999)
