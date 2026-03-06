"""Tests for waitlist management and walk-in queue."""

from datetime import date, timedelta

from openclaw_shared.database import get_db
from medical_dental.clinic_scheduler.scheduling.waitlist import WaitlistManager
from medical_dental.clinic_scheduler.scheduling.walk_in_queue import WalkInQueue


def _setup_doctor(db_path):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO doctors (name_en, specialty, default_slot_duration, active) VALUES (?, ?, ?, ?)",
            ("Dr. Waitlist", "GP", 15, True),
        )
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def test_add_to_waitlist(db_paths):
    db = db_paths["clinic_scheduler"]
    manager = WaitlistManager()
    doctor_id = _setup_doctor(db)
    target = (date.today() + timedelta(days=3)).isoformat()

    wl_id = manager.add_to_waitlist(db, {
        "patient_phone": "+85292222221",
        "patient_name": "Waitlist Patient",
        "doctor_id": doctor_id,
        "preferred_date": target,
        "preferred_session": "morning",
    })
    assert wl_id > 0

    entries = manager.get_waitlist(db, doctor_id=doctor_id)
    assert len(entries) >= 1
    matched = [e for e in entries if e["id"] == wl_id]
    assert len(matched) == 1
    assert matched[0]["patient_phone"] == "+85292222221"
    assert matched[0]["status"] == "waiting"


def test_match_cancellation(db_paths):
    db = db_paths["clinic_scheduler"]
    manager = WaitlistManager()
    doctor_id = _setup_doctor(db)
    target_date = date.today() + timedelta(days=5)

    manager.add_to_waitlist(db, {
        "patient_phone": "+85292222222",
        "patient_name": "Cancel Match",
        "doctor_id": doctor_id,
        "preferred_date": target_date.isoformat(),
        "preferred_session": "morning",
    })

    matches = manager.match_cancellation(db, doctor_id, target_date, session="morning")
    assert len(matches) >= 1
    assert any(m["patient_phone"] == "+85292222222" for m in matches)


def test_walk_in_queue_order(db_paths):
    db = db_paths["clinic_scheduler"]
    queue = WalkInQueue()

    r1 = queue.add_walk_in(db, "Walker One", "+85293333331", "gp")
    r2 = queue.add_walk_in(db, "Walker Two", "+85293333332", "gp")
    r3 = queue.add_walk_in(db, "Walker Three", "+85293333333", "gp")

    assert r1["queue_number"] < r2["queue_number"] < r3["queue_number"]

    current_queue = queue.get_queue(db)
    names = [e["patient_name"] for e in current_queue]
    assert names.index("Walker One") < names.index("Walker Two") < names.index("Walker Three")


def test_walk_in_estimate(db_paths):
    db = db_paths["clinic_scheduler"]
    queue = WalkInQueue(service_durations={"gp": 15, "specialist": 30})

    queue.add_walk_in(db, "Est One", "+85294444441", "gp")
    queue.add_walk_in(db, "Est Two", "+85294444442", "specialist")

    estimate = queue.estimate_wait(db)
    assert estimate >= 45
