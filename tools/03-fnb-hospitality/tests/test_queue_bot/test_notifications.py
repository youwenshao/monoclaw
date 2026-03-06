"""Tests for notification logging."""

from datetime import datetime

from openclaw_shared.database import get_db


class TestNotificationLogging:
    def test_notification_logging(self, db_paths):
        db = db_paths["queue_bot"]
        now = datetime.now().isoformat()

        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO queue_entries
                   (queue_number, guest_name, guest_phone, party_size, status,
                    position_at_join, channel)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (1, "Test Guest", "+85291112222", 2, "notified", 1, "qr"),
            )
            queue_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """INSERT INTO notifications
                   (queue_entry_id, type, channel, sent_at, delivered, message_text)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (queue_id, "table_ready", "whatsapp", now, True, "Your table is ready!"),
            )
            notif_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            row = conn.execute(
                "SELECT * FROM notifications WHERE id = ?", (notif_id,)
            ).fetchone()

        notif = dict(row)
        assert notif["queue_entry_id"] == queue_id
        assert notif["type"] == "table_ready"
        assert notif["channel"] == "whatsapp"
        assert notif["delivered"] == 1
        assert notif["message_text"] == "Your table is ready!"
