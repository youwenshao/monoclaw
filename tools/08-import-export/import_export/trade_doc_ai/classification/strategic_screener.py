"""Strategic commodities screening against HK TID control lists."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("openclaw.trade-doc-ai.screener")

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STRATEGIC_FILE = _DATA_DIR / "strategic_list.json"


class StrategicScreener:
    """Screen product descriptions and HS codes against strategic commodities lists.

    Hong Kong requires a licence from the Trade and Industry Department (TID)
    for strategic commodities.  This screener performs keyword matching against
    the bundled control-list data and flags potential matches.
    """

    def __init__(self) -> None:
        self._categories: list[dict] = []
        self._load_data()

    def _load_data(self) -> None:
        if _STRATEGIC_FILE.exists():
            self._categories = json.loads(
                _STRATEGIC_FILE.read_text(encoding="utf-8")
            )
        else:
            logger.warning("Strategic list file not found at %s", _STRATEGIC_FILE)

    def screen(self, description: str, hs_code: str | None = None) -> dict:
        """Screen a product for strategic commodity controls.

        Returns a dict with:
          - is_strategic (bool): True if any keyword matched
          - category (str | None): matched category name
          - details (str | None): explanation of why it matched
          - matches (list[dict]): all matching categories with their keywords
        """
        if not description:
            return {"is_strategic": False, "category": None, "details": None, "matches": []}

        text = description.lower()
        if hs_code:
            text += " " + hs_code

        all_matches: list[dict] = []

        for cat in self._categories:
            category_name = cat.get("category", "Unknown")
            keywords = cat.get("keywords", [])
            matched_keywords: list[str] = []

            for kw in keywords:
                pattern = re.compile(re.escape(kw.lower()))
                if pattern.search(text):
                    matched_keywords.append(kw)

            if matched_keywords:
                all_matches.append({
                    "category": category_name,
                    "description": cat.get("description", ""),
                    "matched_keywords": matched_keywords,
                })

        if not all_matches:
            return {
                "is_strategic": False,
                "category": None,
                "details": None,
                "matches": [],
            }

        primary = all_matches[0]
        kw_str = ", ".join(primary["matched_keywords"])
        details = (
            f"Matched keywords [{kw_str}] under '{primary['category']}'. "
            f"{primary['description']}. "
            "A Strategic Commodities licence from TID may be required before export."
        )

        return {
            "is_strategic": True,
            "category": primary["category"],
            "details": details,
            "matches": all_matches,
        }
