"""Tests for DefectsManager defects module."""

from openclaw_shared.database import get_db
from construction.defects_manager.defects.dmc_resolver import get_default_matrix


def test_create_property_and_defect(db_paths):
    db = db_paths["defects_manager"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO properties (property_name, property_type, building_age) VALUES (?,?,?)",
            ("Test Block", "residential", 35),
        )
        pid = conn.execute("SELECT id FROM properties").fetchone()["id"]
        conn.execute(
            "INSERT INTO defects (property_id, unit, floor, category, description, priority) "
            "VALUES (?,?,?,?,?,?)",
            (pid, "12A", "12/F", "water_seepage", "Water stain on ceiling", "urgent"),
        )
        defect = conn.execute("SELECT * FROM defects").fetchone()
    assert defect is not None
    assert defect["category"] == "water_seepage"
    assert defect["priority"] == "urgent"


def test_dmc_default_matrix():
    matrix = get_default_matrix()
    assert isinstance(matrix, dict)
    assert "water_seepage" in matrix or "structural" in matrix
    assert len(matrix) > 0


def test_defect_status_values(db_paths):
    db = db_paths["defects_manager"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO properties (property_name, property_type) VALUES (?,?)", ("P1", "residential"))
        pid = conn.execute("SELECT id FROM properties").fetchone()["id"]
        for status in ["reported", "assessed", "work_ordered", "in_progress", "completed", "closed", "referred"]:
            conn.execute(
                "INSERT INTO defects (property_id, category, description, status) VALUES (?,?,?,?)",
                (pid, "other", f"Test {status}", status),
            )
        count = conn.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
    assert count == 7
