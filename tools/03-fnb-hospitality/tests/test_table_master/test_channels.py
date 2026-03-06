"""Tests for booking channel handling (WhatsApp and manual)."""

from datetime import date, timedelta

import pytest
from openclaw_shared.database import get_db


class TestWhatsAppChannel:
    def test_whatsapp_channel_booking(self, db_paths):
        db = db_paths["table_master"]
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO tables
                   (table_number, seats, section, is_combinable, location_type, status)
                   VALUES ('T1', 4, 'main', FALSE, 'standard', 'available')""",
            )
            conn.execute(
                """INSERT INTO bookings
                   (guest_name, guest_phone, party_size, booking_date, booking_time,
                    channel, status, language_pref)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                ("陳大文", "+85291234567", 4, tomorrow, "19:30", "whatsapp", "pending", "zh"),
            )
            bid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            row = conn.execute("SELECT * FROM bookings WHERE id = ?", (bid,)).fetchone()

        booking = dict(row)
        assert booking["channel"] == "whatsapp"
        assert booking["guest_phone"] == "+85291234567"
        assert booking["status"] == "pending"


class TestManualBooking:
    def test_manual_booking_hk_phone_validation(self, db_paths):
        from fnb_hospitality.table_master.channels.manual import ManualBookingRequest

        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        valid = ManualBookingRequest(
            guest_name="Test",
            guest_phone="+85291234567",
            party_size=2,
            booking_date=tomorrow,
            booking_time="19:00",
            channel="phone",
        )
        assert valid.guest_phone == "+85291234567"

        with pytest.raises(Exception):
            ManualBookingRequest(
                guest_name="Test",
                guest_phone="12345",
                party_size=2,
                booking_date=tomorrow,
                booking_time="19:00",
                channel="phone",
            )

        with pytest.raises(Exception):
            ManualBookingRequest(
                guest_name="Test",
                guest_phone="+85291234567",
                party_size=2,
                booking_date=tomorrow,
                booking_time="19:00",
                channel="email",
            )
