"""Cross-reference clients for conflict-of-interest checks."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

from legal.intake_bot.fuzzy_match import combined_match_score

logger = logging.getLogger("openclaw.legal.intake_bot.conflict")


def run_conflict_check(
    matter_id: int,
    db_path: str | Path,
    threshold: float = 0.75,
) -> list[dict[str, Any]]:
    """Cross-reference a matter's client and adverse party against ALL existing clients.

    Performs exact-match, fuzzy, and phonetic comparisons on both English and
    Chinese names.  Returns a list of potential conflicts sorted by score
    descending, each containing:
        match_score, match_type, matched_client_id, matched_client_name,
        checked_name, relationship
    """
    with get_db(db_path) as conn:
        matter_row = conn.execute(
            """SELECT m.id, m.client_id, m.adverse_party_name,
                      m.adverse_party_name_tc, c.name_en, c.name_tc
               FROM matters m
               JOIN clients c ON c.id = m.client_id
               WHERE m.id = ?""",
            (matter_id,),
        ).fetchone()

        if not matter_row:
            return []

        matter = dict(matter_row)

        all_clients = [
            dict(r)
            for r in conn.execute(
                "SELECT id, name_en, name_tc, hkid_last4, phone FROM clients"
            ).fetchall()
        ]

    names_to_check: list[tuple[str, str]] = []

    if matter["name_en"]:
        names_to_check.append((matter["name_en"], "client"))
    if matter["name_tc"]:
        names_to_check.append((matter["name_tc"], "client"))
    if matter["adverse_party_name"]:
        names_to_check.append((matter["adverse_party_name"], "adverse_party"))
    if matter["adverse_party_name_tc"]:
        names_to_check.append((matter["adverse_party_name_tc"], "adverse_party"))

    conflicts: list[dict[str, Any]] = []

    for check_name, relationship in names_to_check:
        for client in all_clients:
            if relationship == "client" and client["id"] == matter["client_id"]:
                continue

            best_score = 0.0
            best_type = "fuzzy"
            matched_name = ""

            for field in ("name_en", "name_tc"):
                existing_name = client.get(field)
                if not existing_name:
                    continue

                score, match_type = combined_match_score(check_name, existing_name)
                if score > best_score:
                    best_score = score
                    best_type = match_type
                    matched_name = existing_name

            if best_score >= threshold:
                conflicts.append({
                    "match_score": round(best_score, 3),
                    "match_type": best_type,
                    "matched_client_id": client["id"],
                    "matched_client_name": matched_name,
                    "checked_name": check_name,
                    "relationship": relationship,
                })

    conflicts.sort(key=lambda c: c["match_score"], reverse=True)

    seen: set[tuple[int, str]] = set()
    deduped: list[dict[str, Any]] = []
    for c in conflicts:
        key = (c["matched_client_id"], c["relationship"])
        if key not in seen:
            seen.add(key)
            deduped.append(c)

    return deduped


def save_conflict_results(
    matter_id: int,
    conflicts: list[dict[str, Any]],
    db_path: str | Path,
) -> int:
    """Persist conflict-check results to the conflict_checks table.

    Returns the number of rows inserted.
    """
    if not conflicts:
        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO conflict_checks
                   (matter_id, checked_against, match_score, match_type, result)
                   VALUES (?, ?, ?, ?, ?)""",
                (matter_id, "all_clients", 0.0, "exact", "clear"),
            )
        return 1

    count = 0
    with get_db(db_path) as conn:
        for c in conflicts:
            result = "potential_conflict" if c["match_score"] < 1.0 else "confirmed_conflict"
            conn.execute(
                """INSERT INTO conflict_checks
                   (matter_id, checked_against, match_score, match_type, result)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    matter_id,
                    c["matched_client_name"],
                    c["match_score"],
                    c["match_type"],
                    result,
                ),
            )
            count += 1

    return count
