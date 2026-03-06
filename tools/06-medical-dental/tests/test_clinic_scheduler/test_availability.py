"""Tests for the scheduling availability engine."""

from datetime import date, timedelta

from openclaw_shared.database import get_db
from medical_dental.clinic_scheduler.scheduling.availability import AvailabilityEngine


def _setup_doctor_schedule(db_path, day_of_week):
    """Insert a doctor with a morning schedule on the given day_of_week."""
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO doctors (name_en, specialty, default_slot_duration, active) VALUES (?, ?, ?, ?)",
            ("Dr. Avail", "GP", 15, True),
        )
        doctor_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute(
            """INSERT INTO schedules
               (doctor_id, day_of_week, session, start_time, end_time, room)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (doctor_id, day_of_week, "morning", "09:00", "13:00", "Room A"),
        )
    return doctor_id


def _find_target_date(day_of_week):
    """Find the next date that falls on the given day_of_week (0=Sun)."""
    today = date.today()
    for delta in range(1, 8):
        candidate = today + timedelta(days=delta)
        if candidate.isoweekday() % 7 == day_of_week:
            return candidate
    return today + timedelta(days=1)


def test_available_slots_no_bookings(db_paths):
    db = db_paths["clinic_scheduler"]
    target_dow = 1  # Monday
    doctor_id = _setup_doctor_schedule(db, target_dow)
    target_date = _find_target_date(target_dow)

    engine = AvailabilityEngine()
    engine.invalidate_cache()
    slots = engine.get_available_slots(db, doctor_id, target_date)

    assert len(slots) > 0
    assert all("start_time" in s and "end_time" in s for s in slots)

    first_slot = slots[0]
    assert first_slot["start_time"] == "09:00"
    assert first_slot["room"] == "Room A"


def test_available_slots_with_booking(db_paths):
    db = db_paths["clinic_scheduler"]
    target_dow = 2  # Tuesday
    doctor_id = _setup_doctor_schedule(db, target_dow)
    target_date = _find_target_date(target_dow)

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO appointments
               (patient_phone, doctor_id, appointment_date, start_time, end_time, status, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("+85200000001", doctor_id, target_date.isoformat(),
             "09:00", "09:15", "booked", "whatsapp"),
        )

    engine = AvailabilityEngine()
    engine.invalidate_cache()
    slots = engine.get_available_slots(db, doctor_id, target_date)

    start_times = [s["start_time"] for s in slots]
    assert "09:00" not in start_times


def test_holiday_blocks_schedule(db_paths):
    db = db_paths["clinic_scheduler"]
    target_dow = 3  # Wednesday
    doctor_id = _setup_doctor_schedule(db, target_dow)
    target_date = _find_target_date(target_dow)

    engine = AvailabilityEngine(holidays=[target_date.isoformat()])
    engine.invalidate_cache()
    slots = engine.get_available_slots(db, doctor_id, target_date)

    assert slots == []


def test_buffer_time_respected(db_paths):
    db = db_paths["clinic_scheduler"]
    target_dow = 4  # Thursday
    doctor_id = _setup_doctor_schedule(db, target_dow)
    target_date = _find_target_date(target_dow)

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO appointments
               (patient_phone, doctor_id, appointment_date, start_time, end_time, status, source)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("+85200000002", doctor_id, target_date.isoformat(),
             "09:00", "09:15", "booked", "whatsapp"),
        )

    engine = AvailabilityEngine()
    engine.invalidate_cache()
    slots = engine.get_available_slots(db, doctor_id, target_date)

    if slots:
        first_available_start = slots[0]["start_time"]
        assert first_available_start >= "09:20", (
            f"First available slot {first_available_start} doesn't respect buffer after 09:15 booking"
        )
