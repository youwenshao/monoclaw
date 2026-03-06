"""Fuzzy drug name matching against the medications database."""

from __future__ import annotations

import logging
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.medical-dental.med_reminder.drug_matcher")

MIN_CONFIDENCE = 0.4


class DrugMatcher:
    """Match OCR-extracted or user-typed drug names to the medications table."""

    def match(self, text: str, db_path: str | Path) -> dict[str, Any]:
        """Find the best-matching medication for *text*.

        Returns:
            {
                "drug_name_en": str | None,
                "drug_name_tc": str | None,
                "confidence": float,
                "medication_id": int | None,
            }
        """
        if not text or not text.strip():
            return _empty_result()

        candidates = self.get_drug_database(db_path)
        if not candidates:
            return _empty_result()

        normalised = text.strip().lower()
        best_score = 0.0
        best_match: dict[str, Any] | None = None

        for drug in candidates:
            score = self._score(normalised, drug)
            if score > best_score:
                best_score = score
                best_match = drug

        if best_match is None or best_score < MIN_CONFIDENCE:
            return _empty_result()

        return {
            "drug_name_en": best_match["drug_name_en"],
            "drug_name_tc": best_match.get("drug_name_tc"),
            "confidence": round(best_score, 2),
            "medication_id": best_match["id"],
        }

    def get_drug_database(self, db_path: str | Path) -> list[dict[str, Any]]:
        """Retrieve all medications from the database."""
        with get_db(db_path) as conn:
            rows = conn.execute(
                "SELECT id, drug_name_en, drug_name_tc, dosage, patient_id FROM medications"
            ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------

    @staticmethod
    def _score(query: str, drug: dict[str, Any]) -> float:
        """Compute a fuzzy similarity score across English and TC names."""
        scores: list[float] = []

        name_en = (drug.get("drug_name_en") or "").lower()
        if name_en:
            scores.append(SequenceMatcher(None, query, name_en).ratio())
            if name_en in query or query in name_en:
                scores.append(0.95)

        name_tc = drug.get("drug_name_tc") or ""
        if name_tc:
            scores.append(SequenceMatcher(None, query, name_tc).ratio())
            if name_tc in query or query in name_tc:
                scores.append(0.95)

        dosage = (drug.get("dosage") or "").lower()
        combined_en = f"{name_en} {dosage}".strip()
        if combined_en:
            scores.append(SequenceMatcher(None, query, combined_en).ratio())

        return max(scores) if scores else 0.0


def _empty_result() -> dict[str, Any]:
    return {
        "drug_name_en": None,
        "drug_name_tc": None,
        "confidence": 0.0,
        "medication_id": None,
    }
