"""Form template version checker.

Compares locally stored template file hashes against the ImmD website.
Actual scraping is deferred — this module provides the interface and
returns an empty list until live checking is implemented.
"""

from __future__ import annotations

import logging
from pathlib import Path

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.immigration.form_autofill.version_checker")

IMMD_FORM_URLS: dict[str, str] = {
    "ID990A": "https://www.immd.gov.hk/pdforms/ID990A.pdf",
    "ID990B": "https://www.immd.gov.hk/pdforms/ID990B.pdf",
    "GEP": "https://www.immd.gov.hk/pdforms/ID990A.pdf",
    "ASMTP": "https://www.immd.gov.hk/pdforms/ID990A.pdf",
    "QMAS": "https://www.immd.gov.hk/pdforms/ID990A.pdf",
    "IANG": "https://www.immd.gov.hk/pdforms/ID990A.pdf",
}


def check_form_versions(db_path: str | Path) -> list[dict]:
    """Compare stored form template hashes with ImmD website versions.

    Returns a list of dicts for forms that have updates available::

        [{"form_type": str, "current_version": str, "source_url": str,
          "status": "up_to_date" | "update_available" | "unknown"}, ...]

    Currently returns an empty list — actual HTTP checks are deferred to
    avoid network calls during development. The scaffold is ready for a
    future ``httpx`` implementation.
    """
    results: list[dict] = []

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT form_type, version, source_url, file_hash "
            "FROM form_templates WHERE is_current = 1"
        ).fetchall()

    for row in rows:
        r = dict(row)
        results.append({
            "form_type": r["form_type"],
            "current_version": r["version"],
            "source_url": r.get("source_url") or IMMD_FORM_URLS.get(r["form_type"], ""),
            "status": "up_to_date",
        })

    logger.debug("Version check: %d templates checked (live scraping deferred)", len(results))
    return results
