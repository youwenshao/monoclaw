"""QuickBooks Online accounting integration stub.

This module provides a placeholder for pushing approved invoices to QuickBooks.
Replace the mock implementation with actual QuickBooks API calls when ready.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("openclaw.accounting.push.quickbooks")


def push_to_quickbooks(invoice_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Push an approved invoice to QuickBooks Online.

    Args:
        invoice_data: Structured invoice dict with supplier_name, invoice_number,
            total_amount, line_items, etc.
        config: QuickBooks configuration with realm_id, client_id, client_secret.

    Returns dict with: success, reference, provider, pushed_at, message.
    """
    realm_id = config.get("realm_id")
    if not realm_id:
        logger.warning("QuickBooks realm_id not configured")
        return {
            "success": False,
            "reference": None,
            "provider": "quickbooks",
            "pushed_at": None,
            "message": "QuickBooks realm_id not configured — skipping push",
        }

    mock_ref = f"QB-{uuid.uuid4().hex[:8].upper()}"
    pushed_at = datetime.utcnow().isoformat()

    logger.info(
        "Mock push to QuickBooks: %s for %s %s (ref: %s)",
        invoice_data.get("invoice_number"),
        invoice_data.get("currency", "HKD"),
        invoice_data.get("total_amount"),
        mock_ref,
    )

    return {
        "success": True,
        "reference": mock_ref,
        "provider": "quickbooks",
        "pushed_at": pushed_at,
        "message": f"Invoice pushed to QuickBooks (mock) — ref {mock_ref}",
    }
