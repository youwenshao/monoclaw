"""Tests for database initialization and schema integrity."""

from __future__ import annotations

from openclaw_shared.database import get_db


def test_all_databases_created(db_paths):
    """All 6 databases should be created."""
    expected = {"visa_doc_ocr", "form_autofill", "client_portal", "policy_watcher", "shared", "mona_events"}
    assert set(db_paths.keys()) == expected
    for name, path in db_paths.items():
        assert path.exists(), f"Database {name} not found at {path}"


def test_visa_doc_ocr_schema(db_paths):
    """VisaDoc OCR tables should exist with correct structure."""
    with get_db(db_paths["visa_doc_ocr"]) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "clients" in tables
    assert "documents" in tables
    assert "scheme_applications" in tables


def test_form_autofill_schema(db_paths):
    """FormAutoFill tables should exist."""
    with get_db(db_paths["form_autofill"]) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "clients" in tables
    assert "applications" in tables
    assert "form_templates" in tables
    assert "field_maps" in tables


def test_client_portal_schema(db_paths):
    """ClientPortal tables should exist."""
    with get_db(db_paths["client_portal"]) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "cases" in tables
    assert "status_history" in tables
    assert "outstanding_documents" in tables
    assert "appointments" in tables
    assert "conversations" in tables


def test_policy_watcher_schema(db_paths):
    """PolicyWatcher tables should exist."""
    with get_db(db_paths["policy_watcher"]) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "policy_sources" in tables
    assert "policy_documents" in tables
    assert "policy_changes" in tables
    assert "alert_subscriptions" in tables
    assert "alert_log" in tables


def test_shared_db_schema(db_paths):
    """Shared DB should have cross-tool client table."""
    with get_db(db_paths["shared"]) as conn:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
    assert "shared_clients" in tables


def test_seed_data(seeded_db_paths):
    """Seeding should populate demo data in all tools."""
    with get_db(seeded_db_paths["visa_doc_ocr"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0] > 0

    with get_db(seeded_db_paths["form_autofill"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM form_templates").fetchone()[0] > 0

    with get_db(seeded_db_paths["client_portal"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM outstanding_documents").fetchone()[0] > 0

    with get_db(seeded_db_paths["policy_watcher"]) as conn:
        assert conn.execute("SELECT COUNT(*) FROM policy_sources").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0] > 0
        assert conn.execute("SELECT COUNT(*) FROM policy_changes").fetchone()[0] > 0


def test_seed_idempotent(seeded_db_paths):
    """Running seed twice should not duplicate data."""
    from immigration.seed_data import seed_all
    counts = seed_all(seeded_db_paths)
    assert all(c == 0 for c in counts.values())
