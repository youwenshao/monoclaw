"""Tests for booking creation and status transitions."""

from datetime import date, timedelta

from openclaw_shared.database import get_db


def _insert_table(conn, table_number="T1", seats=4):
    conn.execute(
        """INSERT INTO tables (table_number, seats, section, is_combinable, location_type, status)
           VALUES (?, ?, 'main', FALSE, 'standard', 'available')""",
        (table_number, seats),
    )
    return conn.execute(
        "SELECT id FROM tables WHERE table_number = ?", (table_number,)
    ).fetchone()[0]


class TestCreateBooking:
    def test_create_booking(self, db_paths):
        db = db_paths["table_master"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            _insert_table(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("陳大文", "+85291234567", 4, tomorrow, "19:30", "whatsapp", "pending", "zh"),
            )

        with get_db(db) as conn:
            row = conn.execute("SELECT * FROM bookings WHERE guest_phone = '+85291234567'").fetchone()
            booking = dict(row)

        assert booking["guest_name"] == "陳大文"
        assert booking["party_size"] == 4
        assert booking["booking_date"] == tomorrow
        assert booking["booking_time"] == "19:30"
        assert booking["channel"] == "whatsapp"
        assert booking["status"] == "pending"

    def test_booking_status_transitions(self, db_paths):
        db = db_paths["table_master"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            _insert_table(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Test Guest", "+85291234567", 2, tomorrow, "20:00", "phone", "pending", "en"),
            )
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute("UPDATE bookings SET status = 'confirmed' WHERE id = ?", (bid,))
            row = conn.execute("SELECT status FROM bookings WHERE id = ?", (bid,)).fetchone()
            assert row[0] == "confirmed"

            conn.execute("UPDATE bookings SET status = 'completed' WHERE id = ?", (bid,))
            row = conn.execute("SELECT status FROM bookings WHERE id = ?", (bid,)).fetchone()
            assert row[0] == "completed"

    def test_booking_with_table_assignment(self, db_paths):
        db = db_paths["table_master"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            table_id = _insert_table(conn, "T5", 6)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    table_id, channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                ("Table Guest", "+85295551234", 4, tomorrow, "19:00", table_id, "phone", "confirmed", "zh"),
            )
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            row = conn.execute("SELECT table_id FROM bookings WHERE id = ?", (bid,)).fetchone()

        assert row[0] == table_id

    def test_booking_language_preference(self, db_paths):
        db = db_paths["table_master"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            _insert_table(conn)
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    channel, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                ("默認語言", "+85261234567", 2, tomorrow, "19:30", "whatsapp", "pending"),
            )
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            row = conn.execute("SELECT language_pref FROM bookings WHERE id = ?", (bid,)).fetchone()

        assert row[0] == "zh", "Default language_pref should be 'zh'"
