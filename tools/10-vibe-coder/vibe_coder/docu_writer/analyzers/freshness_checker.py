"""Check whether documentation is still in sync with the source code.

Computes hashes of code elements and compares them against hashes stored
in the database from the last documentation generation run.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from openclaw_shared.database import get_db

from vibe_coder.docu_writer.analyzers.python_parser import PythonParser
from vibe_coder.docu_writer.analyzers.js_parser import JSParser


@dataclass
class StaleItem:
    file_path: str
    element_name: str
    element_type: str
    reason: str


@dataclass
class FreshnessReport:
    total_checked: int
    stale_count: int
    fresh_count: int
    freshness_ratio: float
    stale_files: list[str] = field(default_factory=list)
    stale_functions: list[StaleItem] = field(default_factory=list)


class FreshnessChecker:
    """Compare current code hashes against stored documentation hashes."""

    def __init__(self) -> None:
        self._py_parser = PythonParser()
        self._js_parser = JSParser()

    def check(self, project_path: str | Path, db_path: str | Path) -> FreshnessReport:
        project_path = Path(project_path).resolve()

        stored = self._load_stored_hashes(db_path, str(project_path))
        current = self._compute_current_hashes(project_path)

        stale_files: set[str] = set()
        stale_items: list[StaleItem] = []
        checked = 0

        all_keys = set(stored.keys()) | set(current.keys())
        for key in all_keys:
            checked += 1
            old_hash = stored.get(key)
            new_hash = current.get(key)

            if old_hash is None:
                fp, name, etype = self._split_key(key)
                stale_items.append(
                    StaleItem(fp, name, etype, reason="new element since last doc gen")
                )
                stale_files.add(fp)
            elif new_hash is None:
                fp, name, etype = self._split_key(key)
                stale_items.append(
                    StaleItem(fp, name, etype, reason="element removed from source")
                )
                stale_files.add(fp)
            elif old_hash != new_hash:
                fp, name, etype = self._split_key(key)
                stale_items.append(
                    StaleItem(fp, name, etype, reason="code changed since last doc gen")
                )
                stale_files.add(fp)

        fresh = checked - len(stale_items)
        ratio = fresh / checked if checked else 1.0

        return FreshnessReport(
            total_checked=checked,
            stale_count=len(stale_items),
            fresh_count=fresh,
            freshness_ratio=round(ratio, 4),
            stale_files=sorted(stale_files),
            stale_functions=stale_items,
        )

    # ------------------------------------------------------------------

    def _load_stored_hashes(self, db_path: str | Path, project_path: str) -> dict[str, str]:
        hashes: dict[str, str] = {}
        with get_db(db_path) as conn:
            rows = conn.execute(
                """SELECT ce.file_path, ce.element_name, ce.element_type, fc.code_hash
                   FROM freshness_checks fc
                   JOIN projects p ON p.id = fc.project_id
                   JOIN code_elements ce ON ce.project_id = p.id
                   WHERE p.project_path = ?""",
                (project_path,),
            ).fetchall()
            for r in rows:
                key = f"{r['file_path']}::{r['element_name']}::{r['element_type']}"
                hashes[key] = r["code_hash"]
        return hashes

    def _compute_current_hashes(self, root: Path) -> dict[str, str]:
        from vibe_coder.docu_writer.analyzers.project_analyzer import LANGUAGE_MAP, IGNORED_DIRS

        hashes: dict[str, str] = {}
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in IGNORED_DIRS for part in path.parts):
                continue
            ext = path.suffix.lower()
            lang = LANGUAGE_MAP.get(ext)
            if lang is None:
                continue

            elements = self._parse(path, lang)
            rel = str(path.relative_to(root))
            for elem in elements:
                content = f"{elem.signature}|{elem.docstring or ''}"
                h = hashlib.sha256(content.encode()).hexdigest()[:16]
                key = f"{rel}::{elem.element_name}::{elem.element_type}"
                hashes[key] = h
        return hashes

    def _parse(self, path: Path, lang: str):
        if lang == "python":
            return self._py_parser.parse(path)
        if lang in ("javascript", "typescript"):
            return self._js_parser.parse(path)
        return []

    @staticmethod
    def _split_key(key: str) -> tuple[str, str, str]:
        parts = key.split("::", 2)
        return parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else ""
