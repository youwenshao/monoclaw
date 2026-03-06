"""Extract structured data from supplier messages."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.supplier-bot.extractor")

DATE_PATTERN = re.compile(
    r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2})\b"
    r"|(\d{1,2}[-/]\d{1,2}[-/]\d{4})\b"
    r"|(\d{1,2}(?:st|nd|rd|th)?\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{4})",
    re.IGNORECASE,
)

QUANTITY_PATTERN = re.compile(
    r"\b(\d[\d,]*)\s*"
    r"(pcs|pieces|units|sets|rolls|pairs|boxes|cartons|pallets|kg|kgs|tons|metres|meters|yards)\b",
    re.IGNORECASE,
)

ISSUE_KEYWORDS = [
    "delay", "delayed", "defect", "defective", "damage", "damaged",
    "shortage", "missing", "problem", "issue", "hold", "held",
    "wrong", "incorrect", "reject", "rejected", "fail", "failed",
    "延迟", "延期", "缺陷", "损坏", "短缺", "问题", "不合格",
]
ISSUE_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(k) for k in ISSUE_KEYWORDS) + r")",
    re.IGNORECASE,
)

DELIVERY_KEYWORDS = re.compile(
    r"(?:deliver|ship|dispatch|发货|出货|到货|ship(?:ped|ping)?|ETA|ETD|arrival|depart)",
    re.IGNORECASE,
)


class InfoExtractor:
    """Extract dates, quantities, issues, and delivery updates from messages."""

    def __init__(self, llm: Any | None = None) -> None:
        self.llm = llm

    def extract(self, message_text: str) -> dict[str, Any]:
        """Extract structured fields from a supplier message.

        Returns a dict with keys: dates, quantities, issues, delivery_update.
        Uses the LLM when available; falls back to regex patterns otherwise.
        """
        if not message_text.strip():
            return {"dates": [], "quantities": [], "issues": [], "delivery_update": None}

        if self.llm is not None:
            return self._extract_with_llm(message_text)

        return self._extract_with_regex(message_text)

    # ------------------------------------------------------------------
    # Regex fallback
    # ------------------------------------------------------------------

    def _extract_with_regex(self, text: str) -> dict[str, Any]:
        dates = self._extract_dates(text)
        quantities = self._extract_quantities(text)
        issues = self._extract_issues(text)
        delivery_update = self._extract_delivery_update(text)

        return {
            "dates": dates,
            "quantities": quantities,
            "issues": issues,
            "delivery_update": delivery_update,
        }

    @staticmethod
    def _extract_dates(text: str) -> list[str]:
        matches = DATE_PATTERN.findall(text)
        results: list[str] = []
        for groups in matches:
            for g in groups:
                if g:
                    results.append(g.strip())
        return results

    @staticmethod
    def _extract_quantities(text: str) -> list[dict[str, str]]:
        matches = QUANTITY_PATTERN.findall(text)
        return [{"amount": m[0].replace(",", ""), "unit": m[1].lower()} for m in matches]

    @staticmethod
    def _extract_issues(text: str) -> list[str]:
        found = ISSUE_PATTERN.findall(text)
        return list(dict.fromkeys(k.lower() for k in found))

    @staticmethod
    def _extract_delivery_update(text: str) -> str | None:
        for line in text.split("\n"):
            if DELIVERY_KEYWORDS.search(line):
                return line.strip()
        return None

    # ------------------------------------------------------------------
    # LLM extraction
    # ------------------------------------------------------------------

    def _extract_with_llm(self, text: str) -> dict[str, Any]:
        prompt = (
            "You are a trade / logistics assistant.  Analyse the following supplier message "
            "and extract structured data in JSON with these keys:\n"
            '  "dates": list of date strings found\n'
            '  "quantities": list of objects with "amount" and "unit"\n'
            '  "issues": list of issue / problem descriptions\n'
            '  "delivery_update": a single sentence summary of any delivery status, or null\n\n'
            "Return ONLY the JSON object.\n\n"
            f"Message:\n{text}"
        )

        try:
            import json
            raw = self.llm.generate(prompt)
            result = raw if isinstance(raw, str) else str(raw)
            data = json.loads(result)
            return {
                "dates": data.get("dates", []),
                "quantities": data.get("quantities", []),
                "issues": data.get("issues", []),
                "delivery_update": data.get("delivery_update"),
            }
        except Exception:
            logger.exception("LLM extraction failed — falling back to regex")
            return self._extract_with_regex(text)
