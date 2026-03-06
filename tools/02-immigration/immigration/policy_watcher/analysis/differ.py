"""Text comparison engine for policy document change detection."""

from __future__ import annotations

import difflib
import hashlib
from typing import Any


def generate_content_hash(text: str) -> str:
    """Generate a SHA-256 hash of normalised text content."""
    normalised = " ".join(text.split()).strip().lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def has_content_changed(old_hash: str, new_hash: str) -> bool:
    """Quick check whether two content hashes differ."""
    return old_hash != new_hash


def compute_diff(old_text: str, new_text: str) -> dict[str, Any]:
    """Three-pass diff between old and new document text.

    Pass 1 — content hash comparison (fast reject for identical content).
    Pass 2 — structural diff via difflib.unified_diff.
    Pass 3 — aggregate statistics: diff_lines, additions, deletions, change_count.
    """
    old_hash = generate_content_hash(old_text)
    new_hash = generate_content_hash(new_text)

    if not has_content_changed(old_hash, new_hash):
        return {
            "changed": False,
            "old_hash": old_hash,
            "new_hash": new_hash,
            "diff_lines": [],
            "additions": [],
            "deletions": [],
            "change_count": 0,
        }

    old_lines = old_text.splitlines(keepends=True)
    new_lines = new_text.splitlines(keepends=True)

    diff_lines = list(difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile="previous",
        tofile="current",
        lineterm="",
    ))

    additions: list[str] = []
    deletions: list[str] = []
    for line in diff_lines:
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            additions.append(line[1:])
        elif line.startswith("-"):
            deletions.append(line[1:])

    change_count = max(len(additions), len(deletions))

    return {
        "changed": True,
        "old_hash": old_hash,
        "new_hash": new_hash,
        "diff_lines": diff_lines,
        "additions": additions,
        "deletions": deletions,
        "change_count": change_count,
    }
