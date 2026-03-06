"""Tradelink EDI connector stub for TDEC electronic filing.

In production, this would integrate with Tradelink's Government Electronic
Trading Services (GETS) API.  For now it returns simulated responses.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

logger = logging.getLogger("openclaw.trade-doc-ai.tradelink")


class TradelinkConnector:
    """Stub connector for Tradelink EDI submission.

    Tradelink (tradelink.com.hk) is HK's primary e-filing gateway for
    trade declarations.  BECS (Business-to-Electronic Commerce System)
    is the alternative.
    """

    def __init__(self, username: str = "", password: str = "") -> None:
        self.username = username
        self.password = password

    def submit(self, declaration_data: dict) -> dict:
        """Submit a TDEC to Tradelink.

        Returns a dict with:
          - status: "submitted" | "validation_error"
          - reference: Tradelink reference number
          - submitted_at: timestamp
          - message: human-readable status message
        """
        ref_hash = hashlib.sha256(
            f"{declaration_data.get('reference_number', '')}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:8].upper()

        reference = f"TL-{datetime.now().strftime('%Y%m%d')}-{ref_hash}"

        validation_errors = self._validate(declaration_data)
        if validation_errors:
            return {
                "status": "validation_error",
                "reference": None,
                "submitted_at": datetime.now().isoformat(),
                "message": f"Validation failed: {'; '.join(validation_errors)}",
                "errors": validation_errors,
            }

        logger.info(
            "STUB: Submitted declaration %s → ref %s",
            declaration_data.get("reference_number", "unknown"),
            reference,
        )

        return {
            "status": "submitted",
            "reference": reference,
            "submitted_at": datetime.now().isoformat(),
            "message": "Declaration submitted successfully (stub mode)",
            "estimated_processing": "1-2 business days",
        }

    def check_status(self, reference: str) -> dict:
        """Check the filing status of a previously submitted declaration.

        In production this polls the Tradelink status API.
        """
        if not reference or not reference.startswith("TL-"):
            return {
                "status": "unknown",
                "reference": reference,
                "message": "Invalid or unknown reference number",
            }

        logger.info("STUB: Checking status for %s", reference)

        return {
            "status": "accepted",
            "reference": reference,
            "checked_at": datetime.now().isoformat(),
            "customs_reference": f"CE-{reference[3:]}",
            "message": "Declaration accepted by Customs & Excise (stub mode)",
        }

    @staticmethod
    def _validate(declaration_data: dict) -> list[str]:
        """Basic validation before submission."""
        errors: list[str] = []

        if not declaration_data.get("declaration_type"):
            errors.append("Missing declaration_type")
        if not declaration_data.get("shipper"):
            errors.append("Missing shipper name")
        if not declaration_data.get("consignee"):
            errors.append("Missing consignee name")
        if not declaration_data.get("items"):
            errors.append("Declaration has no line items")

        items = declaration_data.get("items", [])
        for i, item in enumerate(items):
            if not item.get("hs_code"):
                errors.append(f"Item {i + 1}: missing HS code")
            elif len(item["hs_code"].replace(".", "")) < 6:
                errors.append(f"Item {i + 1}: HS code must be at least 6 digits")

        return errors
