"""Trade terminology glossary for consistent translations."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.supplier-bot.terminology")


class TerminologyManager:
    """Manage a bilingual trade glossary stored in SQLite."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path

    def get_glossary(self) -> list[dict[str, Any]]:
        """Return all glossary entries."""
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM glossary ORDER BY category, term_en"
            ).fetchall()
        return [dict(r) for r in rows]

    def inject_terminology(self, text: str, glossary_terms: list[dict[str, Any]]) -> str:
        """Replace known English terms with preferred translations in-place.

        This is a simple case-insensitive find-and-replace.  The resulting
        text is meant to be passed to the LLM translator so it can see the
        preferred Chinese term alongside the English one, producing more
        consistent output.
        """
        result = text
        for term in glossary_terms:
            en = term.get("term_en", "")
            sc = term.get("term_sc", "")
            if not en or not sc:
                continue
            import re
            pattern = re.compile(re.escape(en), re.IGNORECASE)
            if pattern.search(result):
                replacement = f"{en} ({sc})"
                result = pattern.sub(replacement, result)
        return result

    def add_term(
        self,
        term_en: str,
        term_sc: str,
        term_tc: str | None = None,
        category: str = "general",
        context: str = "",
    ) -> int:
        """Insert a new glossary term and return its ID."""
        with get_db(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO glossary (term_en, term_sc, term_tc, category, context)
                   VALUES (?,?,?,?,?)""",
                (term_en, term_sc, term_tc or term_sc, category, context),
            )
            term_id = cursor.lastrowid
        logger.info("Glossary term added: %s / %s (id=%d)", term_en, term_sc, term_id)
        return term_id  # type: ignore[return-value]

    def search_glossary(self, query: str) -> list[dict[str, Any]]:
        """Search glossary by English or Chinese term (substring match)."""
        pattern = f"%{query}%"
        with get_db(self.db_path) as conn:
            rows = conn.execute(
                """SELECT * FROM glossary
                   WHERE term_en LIKE ? OR term_sc LIKE ? OR term_tc LIKE ?
                   ORDER BY term_en""",
                (pattern, pattern, pattern),
            ).fetchall()
        return [dict(r) for r in rows]
