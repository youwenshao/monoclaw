"""Tests for SiteCoordinator scheduling."""

from openclaw_shared.database import get_db


def test_create_site_and_contractor(db_paths):
    db = db_paths["site_coordinator"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO sites (site_name, district, latitude, longitude, max_daily_workers) VALUES (?,?,?,?,?)",
            ("Test Site", "Sha Tin", 22.38, 114.19, 50),
        )
        conn.execute(
            "INSERT INTO contractors (company_name, trade, team_size) VALUES (?,?,?)",
            ("Test Formwork Co", "formwork", 8),
        )
        site = conn.execute("SELECT * FROM sites").fetchone()
        contractor = conn.execute("SELECT * FROM contractors").fetchone()
    assert site is not None
    assert contractor["trade"] == "formwork"


def test_create_assignment(db_paths):
    db = db_paths["site_coordinator"]
    with get_db(db) as conn:
        conn.execute("INSERT INTO sites (site_name, max_daily_workers) VALUES (?,?)", ("S1", 50))
        sid = conn.execute("SELECT id FROM sites").fetchone()["id"]
        conn.execute("INSERT INTO contractors (company_name, trade) VALUES (?,?)", ("C1", "formwork"))
        cid = conn.execute("SELECT id FROM contractors").fetchone()["id"]
        conn.execute(
            "INSERT INTO schedule_assignments (site_id, contractor_id, assignment_date, trade, status) "
            "VALUES (?,?,?,?,?)",
            (sid, cid, "2026-03-06", "formwork", "scheduled"),
        )
        assignment = conn.execute("SELECT * FROM schedule_assignments").fetchone()
    assert assignment is not None
    assert assignment["status"] == "scheduled"


def test_trade_dependencies(db_paths):
    db = db_paths["site_coordinator"]
    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO trade_dependencies (predecessor_trade, successor_trade, min_gap_days) VALUES (?,?,?)",
            ("formwork", "rebar", 0),
        )
        conn.execute(
            "INSERT INTO trade_dependencies (predecessor_trade, successor_trade, min_gap_days) VALUES (?,?,?)",
            ("rebar", "concreting", 0),
        )
        deps = conn.execute("SELECT * FROM trade_dependencies ORDER BY id").fetchall()
    assert len(deps) == 2
    assert deps[0]["predecessor_trade"] == "formwork"
    assert deps[1]["successor_trade"] == "concreting"
