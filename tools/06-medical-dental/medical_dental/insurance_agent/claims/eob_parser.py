"""Explanation of Benefits (EOB) document parser."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.insurance.eob")

AMOUNT_PATTERN = re.compile(r"HK?\$?\s?([\d,]+(?:\.\d{2})?)")
REF_PATTERN = re.compile(r"(?:CLM|REF|Claim\s*(?:No|Ref))[\s:#-]*([\w-]+)", re.IGNORECASE)


class EobParser:
    """Parse Explanation of Benefits documents to extract structured data.

    Supports LLM-assisted extraction for unstructured text, with a regex
    fallback for common HK insurer EOB formats.
    """

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm

    async def parse_eob(self, pdf_path: str) -> dict[str, Any]:
        """Extract key fields from an EOB PDF.

        Attempts to read the PDF as text first.  Falls back to LLM
        extraction if structured parsing fails.

        Returns dict with: claim_reference, billed_amount, approved_amount,
        patient_responsibility, remarks, raw_text.
        """
        text = self._extract_text_from_pdf(pdf_path)
        if not text:
            return {
                "claim_reference": "",
                "billed_amount": 0.0,
                "approved_amount": 0.0,
                "patient_responsibility": 0.0,
                "remarks": "Unable to extract text from PDF",
                "raw_text": "",
                "source": "error",
            }

        return await self.parse_text(text)

    async def parse_text(self, text: str) -> dict[str, Any]:
        """Parse EOB from plain text content.

        Uses LLM if available, otherwise falls back to regex extraction.
        """
        if self.llm is not None:
            try:
                return await self._llm_parse(text)
            except Exception as exc:
                logger.warning("LLM parsing failed, falling back to regex: %s", exc)

        return self._regex_parse(text)

    async def _llm_parse(self, text: str) -> dict[str, Any]:
        """Use the LLM provider to extract structured fields from EOB text."""
        system_prompt = (
            "You are an insurance document parser for Hong Kong medical/dental claims. "
            "Extract the following fields from the Explanation of Benefits text and "
            "return them as JSON: claim_reference, billed_amount (number), "
            "approved_amount (number), patient_responsibility (number), remarks (string). "
            "All amounts in HKD. If a field is not found, use 0 for numbers and empty string for text."
        )

        response = await self.llm.generate(
            f"Parse this EOB document:\n\n{text[:3000]}",
            system=system_prompt,
            max_tokens=512,
            temperature=0.1,
        )

        import json
        try:
            start = response.index("{")
            end = response.rindex("}") + 1
            parsed = json.loads(response[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning("LLM response was not valid JSON, falling back to regex")
            return self._regex_parse(text)

        return {
            "claim_reference": str(parsed.get("claim_reference", "")),
            "billed_amount": float(parsed.get("billed_amount", 0)),
            "approved_amount": float(parsed.get("approved_amount", 0)),
            "patient_responsibility": float(parsed.get("patient_responsibility", 0)),
            "remarks": str(parsed.get("remarks", "")),
            "raw_text": text[:500],
            "source": "llm",
        }

    def _regex_parse(self, text: str) -> dict[str, Any]:
        """Regex-based fallback for structured EOB formats."""
        ref_match = REF_PATTERN.search(text)
        claim_reference = ref_match.group(1) if ref_match else ""

        amounts = AMOUNT_PATTERN.findall(text)
        parsed_amounts = [float(a.replace(",", "")) for a in amounts]

        billed = parsed_amounts[0] if len(parsed_amounts) > 0 else 0.0
        approved = parsed_amounts[1] if len(parsed_amounts) > 1 else 0.0
        patient_resp = parsed_amounts[2] if len(parsed_amounts) > 2 else billed - approved

        remarks = ""
        for label in ("Remark", "Note", "Comment", "Reason"):
            pattern = re.compile(rf"{label}s?\s*[:\-]\s*(.+?)(?:\n|$)", re.IGNORECASE)
            m = pattern.search(text)
            if m:
                remarks = m.group(1).strip()
                break

        return {
            "claim_reference": claim_reference,
            "billed_amount": billed,
            "approved_amount": approved,
            "patient_responsibility": max(0.0, patient_resp),
            "remarks": remarks,
            "raw_text": text[:500],
            "source": "regex",
        }

    def _extract_text_from_pdf(self, pdf_path: str) -> str:
        """Attempt to read text from a PDF file.

        Tries pdfplumber first, then falls back to a basic read.
        Returns empty string on failure.
        """
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            return "\n".join(pages)
        except ImportError:
            logger.debug("pdfplumber not installed; trying basic text read")
        except Exception as exc:
            logger.warning("pdfplumber failed for %s: %s", pdf_path, exc)

        try:
            with open(pdf_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception as exc:
            logger.warning("Text extraction failed for %s: %s", pdf_path, exc)
            return ""
