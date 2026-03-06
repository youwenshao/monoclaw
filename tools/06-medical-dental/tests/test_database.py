"""Tests for database initialization, schema, and seed data."""

import sqlite3

from openclaw_shared.database import get_db


def test_init_creates_all_databases(db_paths):
    expected = {"insurance_agent", "scribe_ai", "clinic_scheduler", "med_reminder", "shared", "mona_events"}
    assert set(db_paths.keys()) == expected
    for name, path in db_paths.items():
        assert path.exists(), f"{name} database file was not created"


def test_insurance_agent_tables_exist(db_paths):
    expected_tables = {"patients", "insurance_policies", "coverage_details", "claims", "preauthorizations"}
    with get_db(db_paths["insurance_agent"]) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    tables = {r["name"] for r in rows}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_scribe_ai_tables_exist(db_paths):
    expected_tables = {"patients", "consultations", "templates", "custom_vocabulary"}
    with get_db(db_paths["scribe_ai"]) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    tables = {r["name"] for r in rows}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_clinic_scheduler_tables_exist(db_paths):
    expected_tables = {"doctors", "schedules", "appointments", "waitlist"}
    with get_db(db_paths["clinic_scheduler"]) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    tables = {r["name"] for r in rows}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_med_reminder_tables_exist(db_paths):
    expected_tables = {"patients", "medications", "compliance_logs", "refill_requests", "drug_interactions"}
    with get_db(db_paths["med_reminder"]) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    tables = {r["name"] for r in rows}
    assert expected_tables.issubset(tables), f"Missing tables: {expected_tables - tables}"


def test_shared_patients_table(db_paths):
    with get_db(db_paths["shared"]) as conn:
        conn.execute(
            "INSERT INTO shared_patients (phone, name_en, name_tc) VALUES (?, ?, ?)",
            ("+85290001111", "Test Patient", "測試病人"),
        )
        row = conn.execute(
            "SELECT * FROM shared_patients WHERE phone = ?", ("+85290001111",)
        ).fetchone()

    assert row is not None
    assert row["name_en"] == "Test Patient"
    assert row["name_tc"] == "測試病人"
    assert row["phone"] == "+85290001111"


def test_seed_data_populates(seeded_db_paths):
    with get_db(seeded_db_paths["insurance_agent"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM insurance_policies").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM coverage_details").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] > 0

    with get_db(seeded_db_paths["scribe_ai"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM consultations").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM templates").fetchone()[0] > 0

    with get_db(seeded_db_paths["clinic_scheduler"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM doctors").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM schedules").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM appointments").fetchone()[0] > 0

    with get_db(seeded_db_paths["med_reminder"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM medications").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM drug_interactions").fetchone()[0] > 0
