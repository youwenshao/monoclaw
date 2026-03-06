"""Tests for guest profile CRUD and search."""

import pytest
from openclaw_shared.database import get_db

from fnb_hospitality.sommelier_memory.guests.profiles import (
    create_guest,
    delete_guest,
    get_guest,
    search_guests,
    update_guest,
)


def _make_guest(db_path, name="陳大文", phone="+85291234567", **kw):
    return create_guest(db_path, name, phone, **kw)


class TestCreateGuest:
    def test_create_guest(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = _make_guest(db)

        assert guest["name"] == "陳大文"
        assert guest["phone"] == "+85291234567"
        assert guest["id"] is not None
        assert guest["vip_tier"] == "regular"
        assert guest["language_pref"] == "cantonese"

    def test_create_guest_duplicate_phone_raises(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        _make_guest(db)
        with pytest.raises(ValueError, match="already exists"):
            _make_guest(db)


class TestGetGuest:
    def test_get_guest_with_dietary_info(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        created = _make_guest(db)
        gid = created["id"]

        with get_db(db) as conn:
            conn.execute(
                "INSERT INTO dietary_info (guest_id, type, item, severity) VALUES (?,?,?,?)",
                (gid, "allergy", "shellfish", "severe"),
            )

        guest = get_guest(db, gid)
        assert guest["name"] == "陳大文"
        assert len(guest["dietary_info"]) == 1
        assert guest["dietary_info"][0]["item"] == "shellfish"
        assert guest["dietary_info"][0]["severity"] == "severe"

    def test_get_nonexistent_guest(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        guest = get_guest(db, 99999)
        assert guest == {}


class TestUpdateGuest:
    def test_update_guest(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        created = _make_guest(db)
        gid = created["id"]

        updated = update_guest(db, gid, preferred_name="David", vip_tier="vip")
        assert updated["preferred_name"] == "David"
        assert updated["vip_tier"] == "vip"


class TestDeleteGuest:
    def test_delete_guest_pdpo_compliant(self, db_paths):
        """Deletion must cascade to all related tables."""
        db = str(db_paths["sommelier_memory"])
        created = _make_guest(db)
        gid = created["id"]

        with get_db(db) as conn:
            conn.execute(
                "INSERT INTO dietary_info (guest_id, type, item, severity) VALUES (?,?,?,?)",
                (gid, "allergy", "peanuts", "severe"),
            )
            conn.execute(
                "INSERT INTO celebrations (guest_id, event_type, gregorian_date) VALUES (?,?,?)",
                (gid, "birthday", "2026-06-15"),
            )
            conn.execute(
                "INSERT INTO visits (guest_id, visit_date, party_size, total_spend) VALUES (?,?,?,?)",
                (gid, "2026-01-01", 4, 2000.0),
            )
            conn.execute(
                "INSERT INTO preferences (guest_id, category, preference, strength) VALUES (?,?,?,?)",
                (gid, "wine", "Burgundy", "love"),
            )

        result = delete_guest(db, gid)
        assert result is True

        with get_db(db) as conn:
            assert conn.execute("SELECT COUNT(*) FROM sm_guests WHERE id = ?", (gid,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM dietary_info WHERE guest_id = ?", (gid,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM celebrations WHERE guest_id = ?", (gid,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM visits WHERE guest_id = ?", (gid,)).fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM preferences WHERE guest_id = ?", (gid,)).fetchone()[0] == 0


class TestSearchGuests:
    def test_search_guests_by_name(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        _make_guest(db, name="陳大文", phone="+85291234567")
        _make_guest(db, name="Wong Siu Ming", phone="+85298765432")

        results = search_guests(db, "陳")
        assert len(results) >= 1
        assert any(g["name"] == "陳大文" for g in results)

    def test_search_guests_by_tag(self, db_paths):
        db = str(db_paths["sommelier_memory"])
        _make_guest(db, name="Wine Lover", phone="+85291234567", tags="wine lover,regular")
        _make_guest(db, name="Not Tagged", phone="+85298765432")

        results = search_guests(db, "", tags="wine lover")
        assert len(results) >= 1
        assert any(g["name"] == "Wine Lover" for g in results)
