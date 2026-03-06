"""Drug–drug interaction checking against the local interaction database."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.interactions")

SEVERITY_ORDER = ["minor", "moderate", "major", "contraindicated"]


class InteractionChecker:
    """Query the drug_interactions table for known interactions."""

    def check_interactions(
        self,
        db_path: str | Path,
        patient_id: int,
        new_drug: str | None = None,
    ) -> list[dict[str, Any]]:
        """Check all interactions among a patient's active medications.

        If *new_drug* is provided, also checks it against the existing medication list.
        """
        with get_db(db_path) as conn:
            meds = conn.execute(
                "SELECT id, drug_name_en FROM medications WHERE patient_id = ? AND active = 1",
                (patient_id,),
            ).fetchall()

        drug_names = [m["drug_name_en"] for m in meds]
        if new_drug:
            drug_names.append(new_drug)

        interactions: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()

        for i, drug_a in enumerate(drug_names):
            for drug_b in drug_names[i + 1:]:
                pair_key = tuple(sorted((drug_a.lower(), drug_b.lower())))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                result = self.check_pair(db_path, drug_a, drug_b)
                if result:
                    interactions.append(result)

        interactions.sort(
            key=lambda x: SEVERITY_ORDER.index(x.get("severity", "minor"))
            if x.get("severity") in SEVERITY_ORDER
            else -1,
            reverse=True,
        )

        return interactions

    def check_pair(
        self,
        db_path: str | Path,
        drug_a: str,
        drug_b: str,
    ) -> dict[str, Any] | None:
        """Check whether two drugs have a known interaction.

        Matches are case-insensitive and checked in both directions.
        Returns the interaction dict or None.
        """
        with get_db(db_path) as conn:
            row = conn.execute(
                """SELECT * FROM drug_interactions
                   WHERE (LOWER(drug_a) = LOWER(?) AND LOWER(drug_b) = LOWER(?))
                      OR (LOWER(drug_a) = LOWER(?) AND LOWER(drug_b) = LOWER(?))
                   LIMIT 1""",
                (drug_a, drug_b, drug_b, drug_a),
            ).fetchone()

            if row:
                return {
                    "drug_a": row["drug_a"],
                    "drug_b": row["drug_b"],
                    "severity": row["severity"],
                    "description": row["description"],
                    "source": row["source"],
                }

            row = conn.execute(
                """SELECT * FROM drug_interactions
                   WHERE (LOWER(?) LIKE '%' || LOWER(drug_a) || '%' AND LOWER(?) LIKE '%' || LOWER(drug_b) || '%')
                      OR (LOWER(?) LIKE '%' || LOWER(drug_a) || '%' AND LOWER(?) LIKE '%' || LOWER(drug_b) || '%')
                   LIMIT 1""",
                (drug_a, drug_b, drug_b, drug_a),
            ).fetchone()

            if row:
                return {
                    "drug_a": row["drug_a"],
                    "drug_b": row["drug_b"],
                    "severity": row["severity"],
                    "description": row["description"],
                    "source": row["source"],
                }

        return None
