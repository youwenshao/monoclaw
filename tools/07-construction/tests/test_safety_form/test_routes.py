"""Tests for SafetyForm database operations."""

from openclaw_shared.database import get_db


def test_create_site(db_paths):
    db = db_paths["safety_form"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO sites (site_name, address, district, project_type) VALUES (?,?,?,?)",
            ("Test Site", "1 Test Rd", "Sha Tin", "building"),
        )
        row = conn.execute("SELECT * FROM sites WHERE site_name = 'Test Site'").fetchone()
    assert row is not None


def test_create_inspection(db_paths):
    db = db_paths["safety_form"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO sites (site_name) VALUES (?)", ("S1",))
        sid = conn.execute("SELECT id FROM sites").fetchone()["id"]
        conn.execute(
            "INSERT INTO daily_inspections (site_id, inspection_date, inspector) VALUES (?,?,?)",
            (sid, "2026-03-06", "Test Inspector"),
        )
        insp = conn.execute("SELECT * FROM daily_inspections").fetchone()
    assert insp is not None
    assert insp["inspector"] == "Test Inspector"


def test_create_incident(db_paths):
    db = db_paths["safety_form"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO sites (site_name) VALUES (?)", ("S1",))
        sid = conn.execute("SELECT id FROM sites").fetchone()["id"]
        conn.execute(
            "INSERT INTO incidents (site_id, incident_type, description) VALUES (?,?,?)",
            (sid, "near_miss", "Worker slipped on wet surface"),
        )
        row = conn.execute("SELECT * FROM incidents").fetchone()
    assert row is not None
    assert row["incident_type"] == "near_miss"
