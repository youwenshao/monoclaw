"""Tests for database initialization and seed data."""

import tempfile
from pathlib import Path

import pytest


def test_init_all_databases():
    """All 5 databases should be created with correct tables."""
    from real_estate.database import init_all_databases
    with tempfile.TemporaryDirectory() as tmpdir:
        db_paths = init_all_databases(tmpdir)
        assert "property_gpt" in db_paths
        assert "listing_sync" in db_paths
        assert "tenancy_doc" in db_paths
        assert "viewing_bot" in db_paths
        assert "mona_events" in db_paths
        for name, path in db_paths.items():
            assert Path(path).exists(), f"Database {name} not created"


def test_seed_data():
    """Seed data should populate all tool databases."""
    from real_estate.database import init_all_databases
    from real_estate.seed_data import seed_all
    with tempfile.TemporaryDirectory() as tmpdir:
        db_paths = init_all_databases(tmpdir)
        counts = seed_all(db_paths)
        assert counts["property_gpt"] > 0
        assert counts["listing_sync"] > 0
        assert counts["tenancy_doc"] > 0
        assert counts["viewing_bot"] > 0


def test_seed_idempotent():
    """Running seed twice should not duplicate data."""
    from real_estate.database import init_all_databases
    from real_estate.seed_data import seed_all
    with tempfile.TemporaryDirectory() as tmpdir:
        db_paths = init_all_databases(tmpdir)
        counts1 = seed_all(db_paths)
        counts2 = seed_all(db_paths)
        # Second run should seed 0 because data already exists
        for tool, count in counts2.items():
            assert count == 0, f"{tool} seeded {count} records on second run"
