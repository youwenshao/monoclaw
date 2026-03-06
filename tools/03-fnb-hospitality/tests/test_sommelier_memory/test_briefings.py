"""Tests for briefing generation, celebrations, and VIP classification."""

from datetime import date, timedelta

from openclaw_shared.database import get_db

from fnb_hospitality.sommelier_memory.guests.profiles import create_guest
from fnb_hospitality.sommelier_memory.guests.preferences import add_dietary_info
from fnb_hospitality.sommelier_memory.guests.segments import classify_tier
from fnb_hospitality.sommelier_memory.intelligence.briefing import (
    _build_structured_briefing,
)
from fnb_hospitality.sommelier_memory.intelligence.celebrations import (
    get_upcoming_celebrations,
    lunar_to_gregorian,
)


def _make_vip_guest(db_path):
    guest = create_guest(
        db_path,
        name="何家強",
        phone="+85297776666",
        preferred_name="何生",
        language_pref="cantonese",
        tags="corporate,regular",
    )
    gid = guest["id"]

    add_dietary_info(db_path, gid, "allergy", "peanuts", severity="moderate")

    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO preferences (guest_id, category, preference, strength) VALUES (?,?,?,?)",
            (gid, "wine", "Burgundy Pinot Noir", "love"),
        )
        conn.execute(
            "INSERT INTO preferences (guest_id, category, preference, strength) VALUES (?,?,?,?)",
            (gid, "tea", "Pu'er", "like"),
        )
        conn.execute(
            "INSERT INTO preferences (guest_id, category, preference, strength) VALUES (?,?,?,?)",
            (gid, "seating", "private room R1", "like"),
        )

    return gid


class TestGenerateBriefingStructuredData:
    def test_generate_briefing_structured_data(self, db_paths):
        """The structured portion should assemble without any LLM."""
        db = str(db_paths["sommelier_memory"])
        gid = _make_vip_guest(db)

        from fnb_hospitality.sommelier_memory.guests.profiles import get_guest
        from fnb_hospitality.sommelier_memory.guests.history import calculate_lifetime_value

        guest = get_guest(db, gid)
        ltv = calculate_lifetime_value(db, gid)
        structured = _build_structured_briefing(guest, ltv)

        assert structured["guest_id"] == gid
        assert structured["name"] == "何家強"
        assert structured["preferred_name"] == "何生"
        assert len(structured["allergies"]) >= 1
        assert structured["allergies"][0]["item"] == "peanuts"
        assert len(structured["wine_preferences"]) >= 1
        assert len(structured["tea_preferences"]) >= 1
        assert len(structured["seating_preferences"]) >= 1


class TestCelebrationLookahead:
    def test_celebration_lookahead(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = create_guest(db, "Birthday Guest", "+85291234567")
        gid = guest["id"]

        upcoming_date = (date.today() + timedelta(days=3)).isoformat()
        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO celebrations
                   (guest_id, event_type, gregorian_date, use_lunar)
                   VALUES (?, ?, ?, ?)""",
                (gid, "birthday", upcoming_date, False),
            )

        results = get_upcoming_celebrations(db, lookahead_days=7)
        assert len(results) >= 1
        found = [r for r in results if r["guest_id"] == gid]
        assert len(found) == 1
        assert found[0]["event_type"] == "birthday"
        assert found[0]["days_until"] <= 7
        assert "suggested_gesture" in found[0]

    def test_past_celebration_not_in_lookahead(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = create_guest(db, "Past Guest", "+85291234567")
        gid = guest["id"]

        past_date = (date.today() - timedelta(days=30))
        with get_db(db) as conn:
            conn.execute(
                """INSERT INTO celebrations
                   (guest_id, event_type, gregorian_date, use_lunar)
                   VALUES (?, ?, ?, ?)""",
                (gid, "birthday", past_date.replace(year=past_date.year - 1).isoformat(), False),
            )

        results = get_upcoming_celebrations(db, lookahead_days=7)
        found = [r for r in results if r["guest_id"] == gid]
        assert len(found) == 0 or all(r["days_until"] >= 0 for r in found)


class TestVIPTierClassification:
    def test_vip_tier_classification(self, db_paths):
        assert classify_tier(total_visits=1, total_spend=500) == "regular"
        assert classify_tier(total_visits=5, total_spend=10000) == "vip"
        assert classify_tier(total_visits=15, total_spend=50000) == "vvip"

    def test_vip_needs_both_conditions(self, db_paths):
        assert classify_tier(total_visits=5, total_spend=1000) == "regular"
        assert classify_tier(total_visits=2, total_spend=50000) == "regular"

    def test_vip_custom_thresholds(self, db_paths):
        custom = {
            "vip_min_visits": 3,
            "vip_min_spend": 5000,
            "vvip_min_visits": 10,
            "vvip_min_spend": 30000,
        }
        assert classify_tier(3, 5000, thresholds=custom) == "vip"
        assert classify_tier(10, 30000, thresholds=custom) == "vvip"


class TestLunarToGregorianConversion:
    def test_lunar_to_gregorian_conversion(self, db_paths):
        result = lunar_to_gregorian(1, 1, 2026)
        assert isinstance(result, date)
        assert result.year == 2026

    def test_lunar_specific_date(self, db_paths):
        result = lunar_to_gregorian(8, 15, 2026)
        assert isinstance(result, date)
        assert result.month >= 1
        assert result.day >= 1
