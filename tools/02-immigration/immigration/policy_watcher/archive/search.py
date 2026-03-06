"""FTS5-based full-text search over the policy document archive."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.policy_watcher.archive.search")


def _fts5_available(db_path: str | Path) -> bool:
    """Check whether the policy_fts virtual table is usable."""
    try:
        with get_db(db_path) as conn:
            conn.execute("SELECT * FROM policy_fts LIMIT 1")
        return True
    except Exception:
        return False


def _fts5_search(
    db_path: str | Path,
    query: str,
    date_from: str | None,
    date_to: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    fts_query = " OR ".join(
        f'"{term}"' for term in query.split() if term.strip()
    )
    if not fts_query:
        fts_query = f'"{query}"'

    sql = """
        SELECT pd.id, pd.title, pd.title_zh, pd.document_url,
               pd.published_date, pd.scraped_at, pd.gazette_ref,
               snippet(policy_fts, 1, '<mark>', '</mark>', '…', 40) AS snippet,
               rank
        FROM policy_fts
        JOIN policy_documents pd ON pd.id = policy_fts.rowid
        WHERE policy_fts MATCH ?
    """
    params: list[Any] = [fts_query]

    if date_from:
        sql += " AND pd.published_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND pd.published_date <= ?"
        params.append(date_to)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def _like_fallback(
    db_path: str | Path,
    query: str,
    date_from: str | None,
    date_to: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Fallback LIKE search when FTS5 is not available."""
    terms = [t.strip() for t in query.split() if t.strip()]
    if not terms:
        return []

    conditions = []
    params: list[Any] = []
    for term in terms:
        conditions.append("(pd.title LIKE ? OR pd.content_text LIKE ?)")
        params.extend([f"%{term}%", f"%{term}%"])

    where = " OR ".join(conditions)

    sql = f"""
        SELECT pd.id, pd.title, pd.title_zh, pd.document_url,
               pd.published_date, pd.scraped_at, pd.gazette_ref,
               substr(pd.content_text, 1, 200) AS snippet
        FROM policy_documents pd
        WHERE ({where})
    """

    if date_from:
        sql += " AND pd.published_date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND pd.published_date <= ?"
        params.append(date_to)

    sql += " ORDER BY pd.published_date DESC LIMIT ?"
    params.append(limit)

    with get_db(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def search_archive(
    db_path: str | Path,
    query: str,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search the policy document archive using FTS5 with LIKE fallback.

    Returns matching policy documents with highlighted snippets.
    """
    if not query or not query.strip():
        return []

    if _fts5_available(db_path):
        try:
            results = _fts5_search(db_path, query, date_from, date_to, limit)
            logger.debug("FTS5 search for %r returned %d results", query, len(results))
            return results
        except Exception as exc:
            logger.warning("FTS5 search failed (%s), falling back to LIKE", exc)

    results = _like_fallback(db_path, query, date_from, date_to, limit)
    logger.debug("LIKE search for %r returned %d results", query, len(results))
    return results
