"""Xero accounting integration stub.

This module provides a placeholder for pushing approved invoices to Xero.
Replace the mock implementation with actual Xero API calls when ready.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime
from typing import Any

logger = logging.getLogger("openclaw.accounting.push.xero")


def push_to_xero(invoice_data: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """Push an approved invoice to Xero.

    Args:
        invoice_data: Structured invoice dict with supplier_name, invoice_number,
            total_amount, line_items, etc.
        config: Xero API configuration with tenant_id, client_id, client_secret.

    Returns dict with: success, reference, provider, pushed_at, message.
    """
    tenant_id = config.get("tenant_id")
    if not tenant_id:
        logger.warning("Xero tenant_id not configured")
        return {
            "success": False,
            "reference": None,
            "provider": "xero",
            "pushed_at": None,
            "message": "Xero tenant_id not configured — skipping push",
        }

    mock_ref = f"XERO-{uuid.uuid4().hex[:8].upper()}"
    pushed_at = datetime.utcnow().isoformat()

    logger.info(
        "Mock push to Xero: %s for %s %s (ref: %s)",
        invoice_data.get("invoice_number"),
        invoice_data.get("currency", "HKD"),
        invoice_data.get("total_amount"),
        mock_ref,
    )

    return {
        "success": True,
        "reference": mock_ref,
        "provider": "xero",
        "pushed_at": pushed_at,
        "message": f"Invoice pushed to Xero (mock) — ref {mock_ref}",
    }
