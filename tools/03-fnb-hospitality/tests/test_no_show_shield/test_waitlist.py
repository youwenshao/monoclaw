"""Tests for waitlist management and matching."""

from datetime import date, timedelta

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import init_mona_db

from fnb_hospitality.no_show_shield.waitlist.manager import (
    add_to_waitlist,
    find_matching_entries,
)


class TestAddToWaitlist:
    def test_add_to_waitlist(self, db_paths):
        db = str(db_paths["no_show_shield"])
        init_mona_db(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        entry_id = add_to_waitlist(
            db,
            guest_name="Wait Guest",
            guest_phone="+85291234567",
            party_size=4,
            preferred_date=tomorrow,
            preferred_time="19:30",
        )

        assert entry_id > 0

        with get_db(db) as conn:
            row = conn.execute(
                "SELECT * FROM waitlist WHERE id = ?", (entry_id,)
            ).fetchone()

        entry = dict(row)
        assert entry["guest_name"] == "Wait Guest"
        assert entry["party_size"] == 4
        assert entry["status"] == "waiting"
        assert entry["flexibility_minutes"] == 30


class TestFindMatchingWaitlistEntry:
    def test_find_matching_waitlist_entry(self, db_paths):
        db = str(db_paths["no_show_shield"])
        init_mona_db(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        add_to_waitlist(db, "Match Me", "+85291112222", 4, tomorrow, "19:30", flexibility_minutes=30)
        add_to_waitlist(db, "No Match Size", "+85293334444", 10, tomorrow, "19:30")
        add_to_waitlist(db, "No Match Time", "+85295556666", 4, tomorrow, "12:00")

        matches = find_matching_entries(db, tomorrow, "19:30", available_party_size=4)
        assert len(matches) >= 1
        assert matches[0]["guest_name"] == "Match Me"

    def test_find_matching_party_size_tolerance(self, db_paths):
        """Party size ±1 should still match."""
        db = str(db_paths["no_show_shield"])
        init_mona_db(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        add_to_waitlist(db, "Close Size", "+85291112222", 3, tomorrow, "19:30")

        matches = find_matching_entries(db, tomorrow, "19:30", available_party_size=4)
        assert len(matches) >= 1
        names = [m["guest_name"] for m in matches]
        assert "Close Size" in names

    def test_find_matching_time_flexibility(self, db_paths):
        """Within ±30 min flexibility should match."""
        db = str(db_paths["no_show_shield"])
        init_mona_db(db)
        tomorrow = (date.today() + timedelta(days=1)).isoformat()

        add_to_waitlist(db, "Flex Time", "+85291112222", 4, tomorrow, "19:45", flexibility_minutes=30)

        matches = find_matching_entries(db, tomorrow, "19:30", available_party_size=4)
        assert len(matches) >= 1
        names = [m["guest_name"] for m in matches]
        assert "Flex Time" in names
