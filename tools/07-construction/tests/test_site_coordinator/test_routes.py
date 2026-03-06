"""Tests for SiteCoordinator database schema."""

from openclaw_shared.database import get_db


def test_all_tables_exist(db_paths):
    db = db_paths["site_coordinator"]
    expected_tables = {"sites", "contractors", "schedule_assignments", "daily_routes", "trade_dependencies"}
    with get_db(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    assert expected_tables.issubset(tables)


def test_seed_data_populates(seeded_db_paths):
    db = seeded_db_paths["site_coordinator"]
    with get_db(db) as conn:
        sites = conn.execute("SELECT COUNT(*) FROM sites").fetchone()[0]
        contractors = conn.execute("SELECT COUNT(*) FROM contractors").fetchone()[0]
        deps = conn.execute("SELECT COUNT(*) FROM trade_dependencies").fetchone()[0]
    assert sites > 0
    assert contractors > 0
    assert deps > 0
