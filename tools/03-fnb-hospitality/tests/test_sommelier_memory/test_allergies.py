"""Tests for dietary/allergy info management."""

import pytest
from openclaw_shared.database import get_db

from fnb_hospitality.sommelier_memory.guests.profiles import create_guest
from fnb_hospitality.sommelier_memory.guests.preferences import (
    SEVERITY_LEVELS,
    add_dietary_info,
    get_dietary_info,
    remove_dietary_info,
)


def _make_guest(db_path):
    return create_guest(db_path, "Test Guest", "+85291234567")


class TestAddDietaryInfo:
    def test_add_dietary_info(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        gid = guest["id"]

        info = add_dietary_info(db, gid, "allergy", "shellfish", severity="severe")
        assert info["type"] == "allergy"
        assert info["item"] == "shellfish"
        assert info["severity"] == "severe"
        assert info["guest_id"] == gid

    def test_add_dietary_info_invalid_type(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        with pytest.raises(ValueError, match="type must be"):
            add_dietary_info(db, guest["id"], "invalid_type", "item")


class TestAllergySeverityLevels:
    def test_allergy_severity_levels(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        gid = guest["id"]

        for sev in SEVERITY_LEVELS:
            info = add_dietary_info(db, gid, "allergy", f"item_{sev}", severity=sev)
            assert info["severity"] == sev

        all_info = get_dietary_info(db, gid)
        assert len(all_info) == len(SEVERITY_LEVELS)

    def test_invalid_severity_raises(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        with pytest.raises(ValueError, match="severity must be"):
            add_dietary_info(db, guest["id"], "allergy", "item", severity="extreme")


class TestSevereAllergyProtection:
    def test_severe_allergy_cannot_be_hard_deleted(self, db_paths):
        """Severe/anaphylactic allergies must be soft-deleted, not removed from DB."""
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        gid = guest["id"]

        info = add_dietary_info(db, gid, "allergy", "peanuts", severity="severe")
        info_id = info["id"]

        result = remove_dietary_info(db, info_id)
        assert result is True

        with get_db(db) as conn:
            row = conn.execute(
                "SELECT * FROM dietary_info WHERE id = ?", (info_id,)
            ).fetchone()

        assert row is not None, "Severe allergy must NOT be hard-deleted"
        assert "DEACTIVATED" in dict(row)["notes"]

    def test_mild_allergy_can_be_hard_deleted(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)
        gid = guest["id"]

        info = add_dietary_info(db, gid, "allergy", "dust", severity="mild")
        info_id = info["id"]

        remove_dietary_info(db, info_id)

        with get_db(db) as conn:
            row = conn.execute(
                "SELECT * FROM dietary_info WHERE id = ?", (info_id,)
            ).fetchone()
        assert row is None, "Mild allergy should be hard-deleted"
