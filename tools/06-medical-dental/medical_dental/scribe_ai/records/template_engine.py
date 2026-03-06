"""Template engine for pre-defined SOAP note templates."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.scribe-ai.templates")


def _parse_template_row(row: Any) -> dict[str, Any]:
    """Convert a template row to a dict with parsed JSON fields."""
    d = dict(row)
    for json_col in ("soap_template", "common_icd10", "common_medications"):
        if d.get(json_col) and isinstance(d[json_col], str):
            try:
                d[json_col] = json.loads(d[json_col])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


class TemplateEngine:
    """Manage and apply SOAP note templates stored in the database."""

    def get_templates(
        self,
        db_path: str | Path,
        *,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all available templates, optionally filtered by category."""
        if category:
            with get_db(db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM templates WHERE category = ? ORDER BY name",
                    (category,),
                ).fetchall()
        else:
            with get_db(db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM templates ORDER BY category, name"
                ).fetchall()

        return [_parse_template_row(r) for r in rows]

    def get_template(
        self,
        db_path: str | Path,
        template_id: int,
    ) -> dict[str, Any] | None:
        """Retrieve a single template by ID."""
        with get_db(db_path) as conn:
            row = conn.execute(
                "SELECT * FROM templates WHERE id = ?",
                (template_id,),
            ).fetchone()
        if row is None:
            return None
        return _parse_template_row(row)

    def apply_template(
        self,
        template: dict[str, Any],
        overrides: dict[str, str] | None = None,
    ) -> dict[str, str]:
        """Apply overrides to a template's SOAP sections.

        Template placeholders use __ (double underscore) for fill-in-the-blank
        fields. Overrides map SOAP section keys to replacement text.
        Returns a dict with keys: subjective, objective, assessment, plan.
        """
        soap_template = template.get("soap_template", {})
        if isinstance(soap_template, str):
            try:
                soap_template = json.loads(soap_template)
            except (json.JSONDecodeError, TypeError):
                soap_template = {}

        result: dict[str, str] = {
            "subjective": soap_template.get("subjective", ""),
            "objective": soap_template.get("objective", ""),
            "assessment": soap_template.get("assessment", ""),
            "plan": soap_template.get("plan", ""),
        }

        if overrides:
            for section, text in overrides.items():
                if section in result:
                    result[section] = text

        return result
