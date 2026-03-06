"""Glossary CRUD operations for terminology management."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def get_glossary_terms(
    db_path: str | Path,
    domain: str | None = None,
    project_id: int | None = None,
) -> list[dict]:
    """Fetch terms from the glossary_terms table.

    Args:
        db_path: Path to the SQLite database.
        domain: Optional domain filter.
        project_id: Optional project ID to include project-specific terms.

    Returns:
        List of glossary term dicts.
    """
    with get_db(db_path) as conn:
        conditions: list[str] = []
        params: list[Any] = []

        if domain:
            conditions.append("domain = ?")
            params.append(domain)

        if project_id is not None:
            conditions.append("(project_specific = 0 OR project_id = ?)")
            params.append(project_id)
        else:
            conditions.append("project_specific = 0")

        where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
        cursor = conn.execute(
            f"SELECT * FROM glossary_terms{where} ORDER BY domain, term_en",  # noqa: S608
            params,
        )
        return [dict(row) for row in cursor.fetchall()]


def add_glossary_term(
    db_path: str | Path,
    term_en: str,
    term_tc: str,
    term_sc: str,
    domain: str,
    definition: str = "",
    source: str = "",
    project_id: int | None = None,
) -> int:
    """Insert a glossary term and return its ID.

    Args:
        db_path: Path to the SQLite database.
        term_en: English term.
        term_tc: Traditional Chinese term.
        term_sc: Simplified Chinese term.
        domain: Academic domain.
        definition: Optional definition.
        source: Optional source reference.
        project_id: If set, marks the term as project-specific.

    Returns:
        The newly created term's row ID.
    """
    project_specific = 1 if project_id is not None else 0
    with get_db(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO glossary_terms
                (term_en, term_tc, term_sc, domain, definition, source, project_specific, project_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (term_en, term_tc, term_sc, domain, definition, source, project_specific, project_id),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def update_glossary_term(db_path: str | Path, term_id: int, **fields: Any) -> bool:
    """Update one or more fields of a glossary term.

    Args:
        db_path: Path to the SQLite database.
        term_id: ID of the term to update.
        **fields: Column-value pairs to update (e.g. term_en="new value").

    Returns:
        True if a row was updated, False otherwise.
    """
    allowed = {"term_en", "term_tc", "term_sc", "domain", "definition", "source", "project_specific", "project_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{col} = ?" for col in updates)
    params = list(updates.values()) + [term_id]

    with get_db(db_path) as conn:
        cursor = conn.execute(
            f"UPDATE glossary_terms SET {set_clause} WHERE id = ?",  # noqa: S608
            params,
        )
        return cursor.rowcount > 0


def delete_glossary_term(db_path: str | Path, term_id: int) -> bool:
    """Delete a glossary term by ID.

    Args:
        db_path: Path to the SQLite database.
        term_id: ID of the term to delete.

    Returns:
        True if a row was deleted, False otherwise.
    """
    with get_db(db_path) as conn:
        cursor = conn.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))
        return cursor.rowcount > 0


def search_glossary(
    db_path: str | Path,
    query: str,
    domain: str | None = None,
) -> list[dict]:
    """Search glossary terms by partial match across all language columns.

    Args:
        db_path: Path to the SQLite database.
        query: Search string (matched with LIKE %query%).
        domain: Optional domain filter.

    Returns:
        List of matching glossary term dicts.
    """
    like_param = f"%{query}%"
    with get_db(db_path) as conn:
        conditions = ["(term_en LIKE ? OR term_tc LIKE ? OR term_sc LIKE ? OR definition LIKE ?)"]
        params: list[Any] = [like_param, like_param, like_param, like_param]

        if domain:
            conditions.append("domain = ?")
            params.append(domain)

        where = " AND ".join(conditions)
        cursor = conn.execute(
            f"SELECT * FROM glossary_terms WHERE {where} ORDER BY term_en",  # noqa: S608
            params,
        )
        return [dict(row) for row in cursor.fetchall()]
