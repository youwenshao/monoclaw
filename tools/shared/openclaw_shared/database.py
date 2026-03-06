"""SQLite database helpers with schema migration support."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator


@contextmanager
def get_db(db_path: str | Path) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connections with WAL mode and foreign keys."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def run_migrations(db_path: str | Path, schema_sql: str) -> None:
    """Execute a SQL schema string against the database.

    Designed for CREATE TABLE IF NOT EXISTS statements so it's
    safe to run on every startup.
    """
    with get_db(db_path) as conn:
        conn.executescript(schema_sql)


def table_exists(db_path: str | Path, table_name: str) -> bool:
    with get_db(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None


def row_count(db_path: str | Path, table_name: str) -> int:
    with get_db(db_path) as conn:
        cursor = conn.execute(f"SELECT COUNT(*) FROM [{table_name}]")  # noqa: S608
        return cursor.fetchone()[0]
