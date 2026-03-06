"""Tests for queue state machine: join, call, seat, leave, skip, FIFO, typhoon."""

import pytest
from openclaw_shared.database import get_db

from fnb_hospitality.queue_bot.queue.manager import (
    call_next,
    join_queue,
    mark_left,
    seat_guest,
    skip_guest,
    typhoon_clear,
)


def _add_guest(db_path, name, phone, party_size):
    return join_queue(db_path, name, phone, party_size)


class TestJoinQueue:
    def test_join_queue(self, db_paths):
        db = str(db_paths["queue_bot"])
        entry = _add_guest(db, "林小姐", "+85291112222", 2)

        assert entry["queue_number"] >= 1
        assert entry["status"] == "waiting"
        assert entry["guest_name"] == "林小姐"
        assert entry["party_size"] == 2

    def test_join_queue_invalid_phone(self, db_paths):
        db = str(db_paths["queue_bot"])
        with pytest.raises(ValueError, match="Invalid HK phone"):
            join_queue(db, "Bad Phone", "12345", 2)


class TestCallNext:
    def test_call_next(self, db_paths):
        db = str(db_paths["queue_bot"])
        e1 = _add_guest(db, "First", "+85291112222", 2)
        _add_guest(db, "Second", "+85293334444", 3)

        called = call_next(db)
        assert called is not None
        assert called["id"] == e1["id"]
        assert called["status"] == "notified"

    def test_call_next_empty_queue(self, db_paths):
        db = str(db_paths["queue_bot"])
        assert call_next(db) is None


class TestSeatGuest:
    def test_seat_guest(self, db_paths):
        db = str(db_paths["queue_bot"])
        entry = _add_guest(db, "Seater", "+85291112222", 2)
        call_next(db)

        result = seat_guest(db, entry["id"])
        assert result["status"] == "seated"
        assert result["actual_wait_minutes"] is not None
        assert result["actual_wait_minutes"] >= 0


class TestMarkLeft:
    def test_mark_left(self, db_paths):
        db = str(db_paths["queue_bot"])
        entry = _add_guest(db, "Leaver", "+85291112222", 2)

        result = mark_left(db, entry["id"])
        assert result["status"] == "left"
        assert result["left_at"] is not None


class TestSkipGuest:
    def test_skip_guest(self, db_paths):
        db = str(db_paths["queue_bot"])
        e1 = _add_guest(db, "Skipper", "+85291112222", 2)

        import time as _time
        _time.sleep(0.05)
        e2 = _add_guest(db, "Second", "+85293334444", 3)

        skipped = skip_guest(db, e1["id"])
        assert skipped["status"] == "waiting"

        with get_db(db) as conn:
            skipper_ts = conn.execute(
                "SELECT joined_at FROM queue_entries WHERE id = ?", (e1["id"],)
            ).fetchone()[0]
            second_ts = conn.execute(
                "SELECT joined_at FROM queue_entries WHERE id = ?", (e2["id"],)
            ).fetchone()[0]
        assert skipper_ts >= second_ts, (
            "After skip, the skipped entry's joined_at should be updated to current time"
        )


class TestQueueFIFO:
    def test_queue_fifo_ordering(self, db_paths):
        db = str(db_paths["queue_bot"])
        e1 = _add_guest(db, "First", "+85291112222", 2)
        e2 = _add_guest(db, "Second", "+85293334444", 3)
        e3 = _add_guest(db, "Third", "+85295556666", 4)

        c1 = call_next(db)
        assert c1["id"] == e1["id"]

        c2 = call_next(db)
        assert c2["id"] == e2["id"]

        c3 = call_next(db)
        assert c3["id"] == e3["id"]

        assert call_next(db) is None


class TestTyphoonClear:
    def test_typhoon_clear(self, db_paths):
        db = str(db_paths["queue_bot"])
        _add_guest(db, "Guest A", "+85291112222", 2)
        _add_guest(db, "Guest B", "+85293334444", 3)
        _add_guest(db, "Guest C", "+85295556666", 4)

        cleared = typhoon_clear(db)
        assert cleared == 3

        with get_db(db) as conn:
            waiting = conn.execute(
                "SELECT COUNT(*) FROM queue_entries WHERE status = 'waiting'"
            ).fetchone()[0]
        assert waiting == 0
