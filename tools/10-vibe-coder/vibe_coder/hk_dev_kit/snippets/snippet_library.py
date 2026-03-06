"""SQLite-backed snippet search and retrieval."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from openclaw_shared.database import get_db


@dataclass
class Snippet:
    id: int
    title: str
    description: str
    code: str
    language: str = "python"
    category: str = ""
    tags: list[str] = field(default_factory=list)
    usage_count: int = 0


def _row_to_snippet(row: dict) -> Snippet:
    tags_raw = row.get("tags", "[]")
    try:
        tags = json.loads(tags_raw) if isinstance(tags_raw, str) else tags_raw
    except (json.JSONDecodeError, TypeError):
        tags = []
    return Snippet(
        id=row["id"],
        title=row["title"],
        description=row.get("description", ""),
        code=row["code"],
        language=row.get("language", "python"),
        category=row.get("category", ""),
        tags=tags,
        usage_count=row.get("usage_count", 0),
    )


class SnippetLibrary:
    """Search, retrieve, and track usage of HK-specific code snippets."""

    def search(
        self,
        query: str,
        db_path: str | Path,
        category: str | None = None,
    ) -> list[Snippet]:
        """Full-text search across title, description, tags, and code."""
        with get_db(db_path) as conn:
            like = f"%{query}%"
            sql = (
                "SELECT * FROM snippets WHERE "
                "(title LIKE ? OR description LIKE ? OR tags LIKE ? OR code LIKE ?)"
            )
            params: list[str] = [like, like, like, like]

            if category:
                sql += " AND category = ?"
                params.append(category)

            sql += " ORDER BY usage_count DESC"
            rows = conn.execute(sql, params).fetchall()

        return [_row_to_snippet(dict(r)) for r in rows]

    def get_by_id(self, snippet_id: int, db_path: str | Path) -> Snippet | None:
        with get_db(db_path) as conn:
            row = conn.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,)).fetchone()
        return _row_to_snippet(dict(row)) if row else None

    def increment_usage(self, snippet_id: int, db_path: str | Path) -> None:
        with get_db(db_path) as conn:
            conn.execute(
                "UPDATE snippets SET usage_count = usage_count + 1 WHERE id = ?",
                (snippet_id,),
            )

    def list_all(self, db_path: str | Path, category: str | None = None) -> list[Snippet]:
        with get_db(db_path) as conn:
            if category:
                rows = conn.execute(
                    "SELECT * FROM snippets WHERE category = ? ORDER BY usage_count DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute("SELECT * FROM snippets ORDER BY usage_count DESC").fetchall()
        return [_row_to_snippet(dict(r)) for r in rows]
