"""HS code classifier using FTS5 search with optional LLM fallback."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from openclaw_shared.database import get_db

from import_export.trade_doc_ai.classification.hs_database import search_hs_codes

logger = logging.getLogger("openclaw.trade-doc-ai.classifier")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class HSClassifier:
    """Classify product descriptions into Hong Kong HS codes.

    Strategy:
    1. FTS5 search against the hs_code_fts table for fast keyword matching.
    2. If top result confidence is below the ambiguity threshold, use the
       LLM to refine the classification from the candidate shortlist.
    3. Cross-reference with the products table for previously classified goods.
    """

    AMBIGUITY_THRESHOLD = -5.0  # FTS5 rank below which we consider results strong

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = db_path
        self._ensure_fts_populated()

    def _ensure_fts_populated(self) -> None:
        """Seed the FTS table from the bundled JSON if it is empty."""
        with get_db(self.db_path) as conn:
            try:
                count = conn.execute("SELECT COUNT(*) FROM hs_code_fts").fetchone()[0]
            except Exception:
                count = 0

        if count == 0:
            hs_file = _DATA_DIR / "hs_codes_hk.json"
            if hs_file.exists():
                from import_export.trade_doc_ai.classification.hs_database import populate_fts
                codes = json.loads(hs_file.read_text(encoding="utf-8"))
                inserted = populate_fts(self.db_path, codes)
                logger.info("Populated HS FTS table with %d entries", inserted)

    def classify(self, description: str, llm=None) -> list[dict]:
        """Return up to 5 HS code suggestions sorted by confidence (descending).

        Each suggestion is a dict with keys: code, description, confidence.
        Confidence is a float 0.0-1.0 derived from the FTS5 relevance rank.
        """
        if not description or not description.strip():
            return []

        fts_results = search_hs_codes(self.db_path, description, limit=10)

        product_matches = self._search_products(description)

        combined = self._merge_results(fts_results, product_matches)

        if not combined:
            if llm:
                return self._llm_classify(description, llm)
            return []

        top_rank = combined[0]["raw_rank"] if combined else 0
        needs_llm = (
            llm is not None
            and len(combined) >= 2
            and top_rank > self.AMBIGUITY_THRESHOLD
        )

        if needs_llm:
            refined = self._llm_refine(description, combined[:5], llm)
            if refined:
                return refined[:5]

        return [
            {
                "code": r["code"],
                "description": r["description"],
                "confidence": r["confidence"],
            }
            for r in combined[:5]
        ]

    def _search_products(self, description: str) -> list[dict]:
        """Search the products table for previously classified items."""
        tokens = description.strip().split()
        if not tokens:
            return []

        conditions = " OR ".join(
            ["description_en LIKE ?"] * len(tokens)
        )
        params = [f"%{t}%" for t in tokens[:5]]

        with get_db(self.db_path) as conn:
            rows = conn.execute(
                f"""SELECT hs_code, hs_description, description_en
                    FROM products
                    WHERE hs_code IS NOT NULL AND ({conditions})
                    LIMIT 5""",  # noqa: S608
                params,
            ).fetchall()

        return [
            {
                "code": r["hs_code"],
                "description": r["hs_description"] or r["description_en"],
                "source": "product_history",
            }
            for r in rows
        ]

    def _merge_results(
        self, fts_results: list[dict], product_results: list[dict]
    ) -> list[dict]:
        """Merge FTS5 and product-history results, deduplicate by code."""
        seen: set[str] = set()
        merged: list[dict] = []

        for r in fts_results:
            code = r["code"]
            if code in seen:
                continue
            seen.add(code)
            raw_rank = r.get("relevance", 0)
            confidence = self._rank_to_confidence(raw_rank)
            merged.append({
                "code": code,
                "description": r.get("description_en", ""),
                "confidence": confidence,
                "raw_rank": raw_rank,
            })

        for r in product_results:
            code = r["code"]
            if code in seen:
                for m in merged:
                    if m["code"] == code:
                        m["confidence"] = min(1.0, m["confidence"] + 0.15)
                        break
                continue
            seen.add(code)
            merged.append({
                "code": code,
                "description": r["description"],
                "confidence": 0.6,
                "raw_rank": 0,
            })

        merged.sort(key=lambda x: x["confidence"], reverse=True)
        return merged

    @staticmethod
    def _rank_to_confidence(rank: float) -> float:
        """Convert FTS5 BM25 rank (negative, lower = better) to 0..1 confidence."""
        if rank >= 0:
            return 0.3
        normalised = min(abs(rank) / 15.0, 1.0)
        return round(0.3 + normalised * 0.65, 3)

    def _llm_classify(self, description: str, llm) -> list[dict]:
        """Use the LLM to classify when FTS returns no results."""
        prompt = (
            "You are an HS code classification expert for Hong Kong trade declarations.\n"
            f"Product description: {description}\n\n"
            "Return a JSON array of up to 5 suggestions, each with keys:\n"
            '  "code" (8-digit HS code), "description" (English), "confidence" (0.0-1.0)\n'
            "Respond with ONLY the JSON array, no markdown."
        )
        try:
            response = llm.complete(prompt)
            suggestions = json.loads(response)
            for s in suggestions:
                s["confidence"] = float(s.get("confidence", 0.5))
            suggestions.sort(key=lambda x: x["confidence"], reverse=True)
            return suggestions[:5]
        except Exception:
            logger.warning("LLM classification failed for: %s", description)
            return []

    def _llm_refine(
        self, description: str, candidates: list[dict], llm
    ) -> list[dict]:
        """Use the LLM to re-rank ambiguous FTS candidates."""
        candidates_json = json.dumps(
            [{"code": c["code"], "description": c["description"]} for c in candidates],
            ensure_ascii=False,
        )
        prompt = (
            "You are an HS code classification expert for Hong Kong trade declarations.\n"
            f"Product description: {description}\n\n"
            f"Candidate HS codes:\n{candidates_json}\n\n"
            "Re-rank these candidates by relevance. Return a JSON array with keys:\n"
            '  "code", "description", "confidence" (0.0-1.0)\n'
            "Respond with ONLY the JSON array, no markdown."
        )
        try:
            response = llm.complete(prompt)
            refined = json.loads(response)
            for r in refined:
                r["confidence"] = float(r.get("confidence", 0.5))
            refined.sort(key=lambda x: x["confidence"], reverse=True)
            return refined[:5]
        except Exception:
            logger.warning("LLM refinement failed, returning FTS results")
            return []
