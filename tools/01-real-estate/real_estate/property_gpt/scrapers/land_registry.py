"""Placeholder scraper for Hong Kong Land Registry transaction data.

The Land Registry (田土廳) publishes transaction records that can be used
to build a historical price database. This module will contain the scraping
logic once the data source access pattern is finalised.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def scrape_transactions(
    db_path: str | Path,
    *,
    district: str | None = None,
) -> list[dict[str, Any]]:
    """Scrape recent transactions from the Land Registry.

    This is a placeholder — the actual scraping logic is not yet
    implemented pending data-source agreement.

    Returns an empty list until the scraper is wired up.
    """
    logger.info(
        "Land Registry scraper called (district=%s) — not yet implemented",
        district,
    )
    return []
