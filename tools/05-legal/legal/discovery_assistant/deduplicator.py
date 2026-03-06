"""MD5 / SHA-256 hash-based document deduplication."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def compute_hashes(content: str) -> tuple[str, str]:
    """Return (md5_hex, sha256_hex) for the given content string."""
    encoded = content.encode("utf-8")
    md5 = hashlib.md5(encoded).hexdigest()
    sha256 = hashlib.sha256(encoded).hexdigest()
    return md5, sha256


def find_duplicates(db_path: str | Path) -> list[dict[str, Any]]:
    """Scan documents table, group by hash_md5, and return duplicate groups.

    Each entry in the returned list represents a group of documents sharing the
    same MD5 hash.  The first document (by id) in each group is treated as the
    canonical copy; all others are flagged as duplicates.

    Returns list of dicts with:
      - hash_md5: the shared hash
      - canonical_id: id of the earliest document
      - duplicate_ids: list of ids that are duplicates
      - count: total documents in the group
    """
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, hash_md5 FROM documents WHERE hash_md5 IS NOT NULL ORDER BY id"
        ).fetchall()

    groups: dict[str, list[int]] = defaultdict(list)
    for row in rows:
        groups[row["hash_md5"]].append(row["id"])

    duplicates: list[dict[str, Any]] = []
    for hash_md5, ids in groups.items():
        if len(ids) < 2:
            continue
        canonical_id = ids[0]
        duplicate_ids = ids[1:]
        duplicates.append({
            "hash_md5": hash_md5,
            "canonical_id": canonical_id,
            "duplicate_ids": duplicate_ids,
            "count": len(ids),
        })

    return duplicates


def mark_duplicates(db_path: str | Path) -> int:
    """Run dedup scan and update the documents table in-place.

    Sets is_duplicate=1 and duplicate_of for each duplicate document.
    Returns the number of documents marked as duplicates.
    """
    groups = find_duplicates(db_path)
    marked = 0

    with get_db(db_path) as conn:
        for group in groups:
            canonical_id = group["canonical_id"]
            for dup_id in group["duplicate_ids"]:
                conn.execute(
                    "UPDATE documents SET is_duplicate = 1, duplicate_of = ? WHERE id = ?",
                    (canonical_id, dup_id),
                )
                marked += 1

    return marked
