"""Tests for PermitTracker database operations."""

from openclaw_shared.database import get_db


def test_create_project(db_paths):
    db = db_paths["permit_tracker"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO projects (project_name, address, district) VALUES (?,?,?)",
            ("Test Project", "1 Test St", "Central & Western"),
        )
        row = conn.execute("SELECT * FROM projects WHERE project_name = 'Test Project'").fetchone()
    assert row is not None
    assert row["district"] == "Central & Western"


def test_create_submission(db_paths):
    db = db_paths["permit_tracker"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO projects (project_name) VALUES (?)", ("P1",))
        pid = conn.execute("SELECT id FROM projects").fetchone()["id"]
        conn.execute(
            "INSERT INTO submissions (project_id, bd_reference, submission_type, current_status) "
            "VALUES (?,?,?,?)",
            (pid, "BP/2026/0001", "GBP", "Received"),
        )
        sub = conn.execute("SELECT * FROM submissions WHERE bd_reference = 'BP/2026/0001'").fetchone()
    assert sub is not None
    assert sub["submission_type"] == "GBP"


def test_status_history(db_paths):
    db = db_paths["permit_tracker"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO projects (project_name) VALUES (?)", ("P1",))
        pid = conn.execute("SELECT id FROM projects").fetchone()["id"]
        conn.execute(
            "INSERT INTO submissions (project_id, submission_type, current_status) VALUES (?,?,?)",
            (pid, "GBP", "Received"),
        )
        sid = conn.execute("SELECT id FROM submissions").fetchone()["id"]
        conn.execute(
            "INSERT INTO status_history (submission_id, status, status_date) VALUES (?,?,?)",
            (sid, "Received", "2026-01-01"),
        )
        conn.execute(
            "INSERT INTO status_history (submission_id, status, status_date) VALUES (?,?,?)",
            (sid, "Under Examination", "2026-01-15"),
        )
        history = conn.execute(
            "SELECT * FROM status_history WHERE submission_id = ? ORDER BY detected_at",
            (sid,),
        ).fetchall()
    assert len(history) == 2
