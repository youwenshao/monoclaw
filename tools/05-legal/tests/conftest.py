"""Shared test fixtures."""

import sys
import tempfile
from pathlib import Path

import pytest

_tools_dir = Path(__file__).resolve().parent.parent
_shared_dir = _tools_dir.parent / "shared"
sys.path.insert(0, str(_tools_dir))
sys.path.insert(0, str(_shared_dir))


@pytest.fixture
def tmp_workspace():
    """Provide a temporary workspace directory."""
    with tempfile.TemporaryDirectory(prefix="openclaw-test-") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def db_paths(tmp_workspace):
    """Initialize all databases in a temp directory."""
    from legal.database import init_all_databases
    return init_all_databases(str(tmp_workspace))


@pytest.fixture
def seeded_db_paths(db_paths):
    """Databases with demo data seeded."""
    from legal.seed_data import seed_all
    seed_all(db_paths)
    return db_paths
