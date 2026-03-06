"""Tests for DefectsManager database schema."""

from openclaw_shared.database import get_db


def test_all_tables_exist(db_paths):
    db = db_paths["defects_manager"]
    expected_tables = {"properties", "defects", "work_orders", "contractors", "defect_updates"}
    with get_db(db) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        }
    assert expected_tables.issubset(tables)
