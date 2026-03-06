"""Tests for booking conflict detection and capacity checks."""

from datetime import date, timedelta

from openclaw_shared.database import get_db

from fnb_hospitality.table_master.booking.engine import (
    check_capacity,
    detect_conflicts,
    suggest_nearest_slot,
)


def _seed_tables(conn):
    """Insert a set of tables including combinable pairs."""
    tables = [
        ("T1", 2, True, "T2"),
        ("T2", 2, True, "T1"),
        ("T3", 4, False, None),
        ("T4", 6, False, None),
    ]
    for tn, seats, combinable, combine_with in tables:
        conn.execute(
            """INSERT INTO tables
               (table_number, seats, section, is_combinable, combine_with, location_type, status)
               VALUES (?, ?, 'main', ?, ?, 'standard', 'available')""",
            (tn, seats, combinable, combine_with),
        )
    return {
        r[0]: r[1]
        for r in conn.execute("SELECT table_number, id FROM tables").fetchall()
    }


class TestConflictDetection:
    def test_no_conflict_different_tables(self, db_paths):
        db = str(db_paths["table_master"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            ids = _seed_tables(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    table_id, channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Guest A", "+85291234567", 4, tomorrow, "19:30", ids["T3"], "whatsapp", "confirmed", "zh"),
            )

        conflicts = detect_conflicts(db, ids["T4"], tomorrow, "19:30")
        assert conflicts == [], "Different tables should never conflict"

    def test_conflict_same_table_overlapping_time(self, db_paths):
        db = str(db_paths["table_master"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            ids = _seed_tables(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    table_id, channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Guest A", "+85291234567", 4, tomorrow, "19:30", ids["T3"], "phone", "confirmed", "zh"),
            )

        conflicts = detect_conflicts(db, ids["T3"], tomorrow, "19:45")
        assert len(conflicts) > 0, "Same table at overlapping time must conflict"
        assert conflicts[0]["guest_name"] == "Guest A"

    def test_suggest_nearest_slot(self, db_paths):
        db = str(db_paths["table_master"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            ids = _seed_tables(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    end_time, table_id, channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Guest A", "+85291234567", 2, tomorrow, "12:30", "13:45",
                 ids["T3"], "phone", "confirmed", "zh"),
            )

        suggestions = suggest_nearest_slot(
            db, ids["T3"], tomorrow, "12:30", window_minutes=120, step_minutes=15,
        )
        assert len(suggestions) > 0, "Should suggest at least one alternative slot"
        for s in suggestions:
            assert "time" in s
            assert "end_time" in s

    def test_capacity_check_with_combinable_tables(self, db_paths):
        db = str(db_paths["table_master"])
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            _seed_tables(conn)

        result = check_capacity(db, party_size=3, booking_date=tomorrow, booking_time="19:30")
        assert result["available"] is True

        result_large = check_capacity(db, party_size=4, booking_date=tomorrow, booking_time="12:30")
        assert result_large["available"] is True
        if not result_large["direct_tables"]:
            assert len(result_large["combo_tables"]) > 0, (
                "A party of 4 should be served by combining T1+T2 if no single table fits"
            )
