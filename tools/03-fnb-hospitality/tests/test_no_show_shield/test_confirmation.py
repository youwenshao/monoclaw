"""Tests for confirmation step creation and response handling."""

from datetime import datetime

from openclaw_shared.database import get_db


class TestConfirmationStepCreation:
    def test_confirmation_step_creation(self, db_paths):
        db = db_paths["no_show_shield"]

        with get_db(db) as conn:
            for step in (1, 2, 3):
                conn.execute(
                    """INSERT INTO confirmations
                       (booking_id, guest_phone, step, channel, status)
                       VALUES (?, ?, ?, ?, ?)""",
                    (100, "+85291234567", step, "whatsapp", "scheduled"),
                )

            rows = conn.execute(
                "SELECT * FROM confirmations WHERE booking_id = 100 ORDER BY step"
            ).fetchall()

        assert len(rows) == 3
        steps = [dict(r)["step"] for r in rows]
        assert steps == [1, 2, 3]
        for r in rows:
            assert dict(r)["status"] == "scheduled"
            assert dict(r)["guest_phone"] == "+85291234567"


class TestConfirmationResponse:
    def test_confirmation_response_marks_confirmed(self, db_paths):
        db = db_paths["no_show_shield"]
        now = datetime.now().isoformat()

        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO confirmations
                   (booking_id, guest_phone, step, channel, status, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (200, "+85298765432", 1, "whatsapp", "sent", now),
            )
            conf_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            conn.execute(
                """UPDATE confirmations
                   SET response = 'confirmed', responded_at = ?, status = 'confirmed'
                   WHERE id = ?""",
                (now, conf_id),
            )
            row = conn.execute(
                "SELECT * FROM confirmations WHERE id = ?", (conf_id,)
            ).fetchone()

        conf = dict(row)
        assert conf["response"] == "confirmed"
        assert conf["status"] == "confirmed"
        assert conf["responded_at"] is not None
