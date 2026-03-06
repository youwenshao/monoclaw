"""Bupa HK insurance portal connector (structured stub)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from medical_dental.insurance_agent.verification.generic_connector import (
    CoverageResult,
    GenericConnector,
)

logger = logging.getLogger("openclaw.medical-dental.insurance.bupa")

BUPA_PORTAL_URL = "https://www.bupa.com.hk/en/member-login"

BUPA_PREAUTH_CATEGORIES = frozenset({
    "dental_major",
    "surgery",
    "hospitalisation",
    "mri_ct_scan",
    "physiotherapy_extended",
})

BUPA_PLAN_BENEFITS: dict[str, list[dict[str, Any]]] = {
    "comprehensive": [
        {"category": "gp_consultation", "sub_limit": 800, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "specialist", "sub_limit": 2000, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 1500, "copay_pct": 0, "copay_fixed": 200, "deductible": 0},
        {"category": "dental_major", "sub_limit": 5000, "copay_pct": 30, "copay_fixed": 0, "deductible": 500},
        {"category": "hospitalisation", "sub_limit": 100000, "copay_pct": 10, "copay_fixed": 0, "deductible": 2000},
    ],
    "standard": [
        {"category": "gp_consultation", "sub_limit": 500, "copay_pct": 0, "copay_fixed": 50, "deductible": 0},
        {"category": "specialist", "sub_limit": 1200, "copay_pct": 30, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 800, "copay_pct": 0, "copay_fixed": 300, "deductible": 0},
    ],
    "executive": [
        {"category": "gp_consultation", "sub_limit": 1200, "copay_pct": 0, "copay_fixed": 0, "deductible": 0},
        {"category": "specialist", "sub_limit": 3000, "copay_pct": 10, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 3000, "copay_pct": 0, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_major", "sub_limit": 10000, "copay_pct": 20, "copay_fixed": 0, "deductible": 500},
        {"category": "hospitalisation", "sub_limit": 250000, "copay_pct": 0, "copay_fixed": 0, "deductible": 5000},
    ],
}


def _simulated_portal_response(policy_number: str, member_id: str) -> dict[str, Any]:
    """Simulate the structured data that would come from parsing the Bupa portal."""
    is_active = not policy_number.endswith("INVALID")
    plan = "comprehensive"
    if "STD" in policy_number:
        plan = "standard"
    elif "EXEC" in policy_number or "005678" in policy_number:
        plan = "executive"

    annual_limit = {"comprehensive": 200000, "standard": 100000, "executive": 500000}[plan]
    used_ratio = random.uniform(0.05, 0.35)

    return {
        "portal_status": "active" if is_active else "inactive",
        "plan_name": f"Bupa {plan.title()} Medical",
        "plan_type": plan,
        "policy_holder": member_id,
        "annual_limit": annual_limit,
        "year_to_date_used": round(annual_limit * used_ratio, 2),
        "effective_date": "2024-01-01",
        "expiry_date": "2026-12-31",
    }


class BupaConnector(GenericConnector):
    """Connector for Bupa Hong Kong insurance portal.

    This is a structured stub — actual portal scraping would use
    Playwright to log in and extract data.  The screenshot-on-failure
    path is recorded but no real browser is launched.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 1.5

    def __init__(
        self,
        rate_limit_seconds: float = 2.0,
        screenshot_dir: str = "/tmp/bupa_screenshots",
    ) -> None:
        super().__init__(
            insurer_name="bupa",
            portal_url=BUPA_PORTAL_URL,
            rate_limit_seconds=rate_limit_seconds,
            screenshot_dir=screenshot_dir,
        )

    def _retry_with_backoff(self, fn: Any, *args: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return fn(*args)
            except Exception as exc:
                last_exc = exc
                wait = self.BACKOFF_BASE ** attempt
                logger.warning(
                    "Bupa attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt + 1, self.MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        self._record_screenshot_path(f"bupa_failure_{int(time.time())}.png")
        raise last_exc  # type: ignore[misc]

    def _record_screenshot_path(self, filename: str) -> str:
        path = f"{self.screenshot_dir}/{filename}"
        logger.info("Screenshot would be saved to %s", path)
        return path

    def _parse_portal_response(self, raw: dict[str, Any], policy_number: str, member_id: str) -> CoverageResult:
        status_map = {"active": "active", "inactive": "expired", "suspended": "suspended"}
        portal_status = raw.get("portal_status", "unknown")
        mapped_status = status_map.get(portal_status, "unknown")

        annual_limit = raw.get("annual_limit", 0)
        used = raw.get("year_to_date_used", 0)

        plan_type = raw.get("plan_type", "standard")
        benefits = BUPA_PLAN_BENEFITS.get(plan_type, BUPA_PLAN_BENEFITS["standard"])

        return CoverageResult(
            policy_number=policy_number,
            member_id=member_id,
            status=mapped_status,
            plan_type=plan_type,
            annual_limit=annual_limit,
            remaining_balance=round(annual_limit - used, 2),
            benefits=benefits,
            raw_response=raw,
        )

    def _do_verify(self, policy_number: str, member_id: str) -> CoverageResult:
        raw = self._retry_with_backoff(_simulated_portal_response, policy_number, member_id)
        return self._parse_portal_response(raw, policy_number, member_id)

    def _do_check_preauth(self, benefit_category: str) -> bool:
        return benefit_category in BUPA_PREAUTH_CATEGORIES

    def _do_get_benefits(self, policy_id: str) -> list[dict[str, Any]]:
        plan_type = "comprehensive"
        if "STD" in policy_id:
            plan_type = "standard"
        elif "EXEC" in policy_id or "005678" in policy_id:
            plan_type = "executive"
        return list(BUPA_PLAN_BENEFITS.get(plan_type, BUPA_PLAN_BENEFITS["standard"]))
