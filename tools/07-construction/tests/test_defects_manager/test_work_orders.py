"""Tests for DefectsManager work orders."""

from openclaw_shared.database import get_db


def test_create_contractor(db_paths):
    db = db_paths["defects_manager"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO contractors (company_name, phone, trades, performance_score) VALUES (?,?,?,?)",
            ("Test Plumbing Co", "+85291234567", '["plumbing"]', 4.5),
        )
        row = conn.execute("SELECT * FROM contractors").fetchone()
    assert row is not None
    assert row["performance_score"] == 4.5


def test_create_work_order(db_paths):
    db = db_paths["defects_manager"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO properties (property_name, property_type) VALUES (?,?)", ("P1", "residential"))
        pid = conn.execute("SELECT id FROM properties").fetchone()["id"]
        conn.execute(
            "INSERT INTO defects (property_id, category, description) VALUES (?,?,?)",
            (pid, "plumbing", "Leaking pipe"),
        )
        did = conn.execute("SELECT id FROM defects").fetchone()["id"]
        conn.execute(
            "INSERT INTO contractors (company_name, trades) VALUES (?,?)",
            ("Plumber Co", '["plumbing"]'),
        )
        cid = conn.execute("SELECT id FROM contractors").fetchone()["id"]
        conn.execute(
            "INSERT INTO work_orders (defect_id, contractor_id, scope_of_work, status) VALUES (?,?,?,?)",
            (did, cid, "Fix leaking pipe", "draft"),
        )
        wo = conn.execute("SELECT * FROM work_orders").fetchone()
    assert wo is not None
    assert wo["status"] == "draft"


def test_work_order_status_transitions(db_paths):
    db = db_paths["defects_manager"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO properties (property_name, property_type) VALUES (?,?)", ("P1", "residential"))
        pid = conn.execute("SELECT id FROM properties").fetchone()["id"]
        conn.execute("INSERT INTO defects (property_id, category, description) VALUES (?,?,?)", (pid, "other", "Test"))
        did = conn.execute("SELECT id FROM defects").fetchone()["id"]
        conn.execute("INSERT INTO work_orders (defect_id, status) VALUES (?,?)", (did, "draft"))
        woid = conn.execute("SELECT id FROM work_orders").fetchone()["id"]

        for status in ["issued", "accepted", "in_progress", "completed", "signed_off"]:
            conn.execute("UPDATE work_orders SET status = ? WHERE id = ?", (status, woid))

        wo = conn.execute("SELECT * FROM work_orders WHERE id = ?", (woid,)).fetchone()
    assert wo["status"] == "signed_off"
