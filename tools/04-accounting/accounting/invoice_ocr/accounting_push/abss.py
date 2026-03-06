"""ABSS (formerly MYOB) accounting integration stub.

This module provides a placeholder for pushing approved invoices to ABSS.
Replace the mock implementation with actual ABSS API calls when ready.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("openclaw.accounting.push.abss")


def push_to_abss(invoice_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Push an approved invoice to ABSS.

    Args:
        invoice_data: Structured invoice dict with supplier_name, invoice_number,
            total_amount, line_items, etc.
        config: ABSS configuration with company_file, username, password.

    Returns dict with: success, reference, provider, pushed_at, message.
    """
    company_file = config.get("company_file")
    if not company_file:
        logger.warning("ABSS company_file not configured")
        return {
            "success": False,
            "reference": None,
            "provider": "abss",
            "pushed_at": None,
            "message": "ABSS company_file not configured — skipping push",
        }

    mock_ref = f"ABSS-{uuid.uuid4().hex[:8].upper()}"
    pushed_at = datetime.utcnow().isoformat()

    logger.info(
        "Mock push to ABSS: %s for %s %s (ref: %s)",
        invoice_data.get("invoice_number"),
        invoice_data.get("currency", "HKD"),
        invoice_data.get("total_amount"),
        mock_ref,
    )

    return {
        "success": True,
        "reference": mock_ref,
        "provider": "abss",
        "pushed_at": pushed_at,
        "message": f"Invoice pushed to ABSS (mock) — ref {mock_ref}",
    }
