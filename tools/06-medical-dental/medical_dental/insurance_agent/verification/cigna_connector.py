"""Cigna HK insurance portal connector (structured stub)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from medical_dental.insurance_agent.verification.generic_connector import (
    CoverageResult,
    GenericConnector,
)

logger = logging.getLogger("openclaw.medical-dental.insurance.cigna")

CIGNA_PORTAL_URL = "https://www.cigna.com.hk/member-area/login"

CIGNA_PREAUTH_CATEGORIES = frozenset({
    "dental_major",
    "surgery",
    "hospitalisation",
    "advanced_diagnostics",
    "rehabilitation",
})

CIGNA_PLAN_BENEFITS: dict[str, list[dict[str, Any]]] = {
    "individual": [
        {"category": "gp_consultation", "sub_limit": 600, "copay_pct": 0, "copay_fixed": 100, "deductible": 0},
        {"category": "specialist", "sub_limit": 1500, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 1000, "copay_pct": 0, "copay_fixed": 200, "deductible": 0},
        {"category": "dental_major", "sub_limit": 5000, "copay_pct": 30, "copay_fixed": 0, "deductible": 500},
    ],
    "group": [
        {"category": "gp_consultation", "sub_limit": 700, "copay_pct": 10, "copay_fixed": 0, "deductible": 0},
        {"category": "specialist", "sub_limit": 1800, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 1500, "copay_pct": 0, "copay_fixed": 150, "deductible": 0},
        {"category": "dental_major", "sub_limit": 8000, "copay_pct": 25, "copay_fixed": 0, "deductible": 500},
        {"category": "hospitalisation", "sub_limit": 200000, "copay_pct": 10, "copay_fixed": 0, "deductible": 3000},
    ],
    "global": [
        {"category": "gp_consultation", "sub_limit": 1000, "copay_pct": 0, "copay_fixed": 0, "deductible": 0},
        {"category": "specialist", "sub_limit": 3000, "copay_pct": 10, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 3000, "copay_pct": 0, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_major", "sub_limit": 15000, "copay_pct": 20, "copay_fixed": 0, "deductible": 500},
        {"category": "hospitalisation", "sub_limit": 500000, "copay_pct": 0, "copay_fixed": 0, "deductible": 5000},
    ],
}


def _simulated_portal_response(policy_number: str, member_id: str) -> dict[str, Any]:
    """Simulate parsing data from the Cigna member portal."""
    is_active = not policy_number.endswith("INVALID")
    plan = "individual"
    if "GRP" in policy_number:
        plan = "group"
    elif "GLB" in policy_number:
        plan = "global"

    limits = {"individual": 150000, "group": 200000, "global": 500000}
    annual_limit = limits[plan]
    used_ratio = random.uniform(0.03, 0.30)

    return {
        "enrollment_status": "Enrolled" if is_active else "Terminated",
        "benefit_plan": f"Cigna {plan.title()} Health Plan",
        "plan_tier": plan,
        "cigna_member_id": member_id,
        "policy_reference": policy_number,
        "annual_maximum": annual_limit,
        "utilised_amount": round(annual_limit * used_ratio, 2),
        "next_renewal": "2025-12-31",
    }


class CignaConnector(GenericConnector):
    """Connector for Cigna Hong Kong insurance portal.

    Structured stub with retry/backoff and screenshot-on-failure pattern.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 1.5

    def __init__(
        self,
        rate_limit_seconds: float = 2.0,
        screenshot_dir: str = "/tmp/cigna_screenshots",
    ) -> None:
        super().__init__(
            insurer_name="cigna",
            portal_url=CIGNA_PORTAL_URL,
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
                    "Cigna attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt + 1, self.MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        self._record_screenshot_path(f"cigna_failure_{int(time.time())}.png")
        raise last_exc  # type: ignore[misc]

    def _record_screenshot_path(self, filename: str) -> str:
        path = f"{self.screenshot_dir}/{filename}"
        logger.info("Screenshot would be saved to %s", path)
        return path

    def _parse_portal_response(self, raw: dict[str, Any], policy_number: str, member_id: str) -> CoverageResult:
        status_map = {"Enrolled": "active", "Terminated": "expired", "On Hold": "suspended"}
        enrollment = raw.get("enrollment_status", "Unknown")
        mapped = status_map.get(enrollment, "unknown")

        annual_max = raw.get("annual_maximum", 0)
        utilised = raw.get("utilised_amount", 0)
        plan_tier = raw.get("plan_tier", "individual")
        benefits = CIGNA_PLAN_BENEFITS.get(plan_tier, CIGNA_PLAN_BENEFITS["individual"])

        return CoverageResult(
            policy_number=policy_number,
            member_id=member_id,
            status=mapped,
            plan_type=plan_tier,
            annual_limit=annual_max,
            remaining_balance=round(annual_max - utilised, 2),
            benefits=benefits,
            raw_response=raw,
        )

    def _do_verify(self, policy_number: str, member_id: str) -> CoverageResult:
        raw = self._retry_with_backoff(_simulated_portal_response, policy_number, member_id)
        return self._parse_portal_response(raw, policy_number, member_id)

    def _do_check_preauth(self, benefit_category: str) -> bool:
        return benefit_category in CIGNA_PREAUTH_CATEGORIES

    def _do_get_benefits(self, policy_id: str) -> list[dict[str, Any]]:
        plan = "individual"
        if "GRP" in policy_id:
            plan = "group"
        elif "GLB" in policy_id:
            plan = "global"
        return list(CIGNA_PLAN_BENEFITS.get(plan, CIGNA_PLAN_BENEFITS["individual"]))
