"""FTS5-backed HS code database for fast full-text search."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from openclaw_shared.database import get_db


def search_hs_codes(db_path: str | Path, query: str, limit: int = 10) -> list[dict]:
    """Full-text search over the hs_code_fts virtual table.

    Returns results ranked by BM25 relevance, each containing
    code, description_en, description_tc, and a relevance rank.
    """
    if not query or not query.strip():
        return []

    tokens = query.strip().split()
    fts_query = " OR ".join(tokens)

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT code, description_en, description_tc,
                      rank AS relevance
               FROM hs_code_fts
               WHERE hs_code_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()

    return [dict(r) for r in rows]


def get_hs_code(db_path: str | Path, code: str) -> dict | None:
    """Look up a specific HS code by exact code match."""
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT code, description_en, description_tc FROM hs_code_fts WHERE code = ?",
            (code,),
        ).fetchone()
    return dict(row) if row else None


def populate_fts(db_path: str | Path, codes: list[dict]) -> int:
    """Bulk-insert HS code entries into the FTS5 table.

    Each dict should have keys: code, description_en, description_tc.
    Existing entries with matching codes are skipped.
    Returns the number of rows actually inserted.
    """
    if not codes:
        return 0

    inserted = 0
    with get_db(db_path) as conn:
        existing_codes: set[str] = set()
        try:
            rows = conn.execute("SELECT code FROM hs_code_fts").fetchall()
            existing_codes = {r[0] for r in rows}
        except sqlite3.OperationalError:
            pass

        for entry in codes:
            code = entry.get("code", "")
            if code in existing_codes:
                continue
            conn.execute(
                "INSERT INTO hs_code_fts (code, description_en, description_tc) VALUES (?, ?, ?)",
                (code, entry.get("description_en", ""), entry.get("description_tc", "")),
            )
            inserted += 1

    return inserted
