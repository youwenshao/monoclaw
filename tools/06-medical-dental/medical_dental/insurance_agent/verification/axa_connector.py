"""AXA HK insurance portal connector (structured stub)."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

from medical_dental.insurance_agent.verification.generic_connector import (
    CoverageResult,
    GenericConnector,
)

logger = logging.getLogger("openclaw.medical-dental.insurance.axa")

AXA_PORTAL_URL = "https://emma.axa.com.hk/login"

AXA_PREAUTH_CATEGORIES = frozenset({
    "dental_major",
    "surgery",
    "hospitalisation",
    "maternity",
})

AXA_PLAN_BENEFITS: dict[str, list[dict[str, Any]]] = {
    "standard": [
        {"category": "gp_consultation", "sub_limit": 500, "copay_pct": 0, "copay_fixed": 50, "deductible": 0},
        {"category": "specialist", "sub_limit": 1200, "copay_pct": 30, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 800, "copay_pct": 0, "copay_fixed": 250, "deductible": 0},
    ],
    "premium": [
        {"category": "gp_consultation", "sub_limit": 800, "copay_pct": 10, "copay_fixed": 0, "deductible": 0},
        {"category": "specialist", "sub_limit": 2000, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 2000, "copay_pct": 0, "copay_fixed": 100, "deductible": 0},
        {"category": "dental_major", "sub_limit": 8000, "copay_pct": 25, "copay_fixed": 0, "deductible": 500},
        {"category": "hospitalisation", "sub_limit": 150000, "copay_pct": 10, "copay_fixed": 0, "deductible": 3000},
    ],
    "senior": [
        {"category": "gp_consultation", "sub_limit": 600, "copay_pct": 0, "copay_fixed": 80, "deductible": 0},
        {"category": "specialist", "sub_limit": 1500, "copay_pct": 20, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 1000, "copay_pct": 0, "copay_fixed": 200, "deductible": 0},
    ],
    "individual": [
        {"category": "gp_consultation", "sub_limit": 600, "copay_pct": 0, "copay_fixed": 100, "deductible": 0},
        {"category": "specialist", "sub_limit": 1500, "copay_pct": 25, "copay_fixed": 0, "deductible": 0},
        {"category": "dental_basic", "sub_limit": 1000, "copay_pct": 0, "copay_fixed": 200, "deductible": 0},
    ],
}


def _simulated_portal_response(policy_number: str, member_id: str) -> dict[str, Any]:
    """Simulate parsing data from AXA Emma portal."""
    is_active = not policy_number.endswith("INVALID")
    plan = "standard"
    if "SEN" in policy_number:
        plan = "senior"
    elif "PREM" in policy_number:
        plan = "premium"
    elif "IND" in policy_number:
        plan = "individual"

    limits = {"standard": 100000, "premium": 250000, "senior": 80000, "individual": 120000}
    annual_limit = limits[plan]
    used_ratio = random.uniform(0.05, 0.40)

    return {
        "member_status": "Active" if is_active else "Terminated",
        "plan_description": f"AXA {plan.title()} Medical Plan",
        "plan_code": plan,
        "member_number": member_id,
        "policy_ref": policy_number,
        "overall_limit": annual_limit,
        "claims_ytd": round(annual_limit * used_ratio, 2),
        "renewal_date": "2026-04-01",
    }


class AxaConnector(GenericConnector):
    """Connector for AXA Hong Kong (Emma) insurance portal.

    Structured stub with retry/backoff and screenshot-on-failure pattern.
    """

    MAX_RETRIES = 3
    BACKOFF_BASE = 1.5

    def __init__(
        self,
        rate_limit_seconds: float = 2.0,
        screenshot_dir: str = "/tmp/axa_screenshots",
    ) -> None:
        super().__init__(
            insurer_name="axa",
            portal_url=AXA_PORTAL_URL,
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
                    "AXA attempt %d/%d failed: %s — retrying in %.1fs",
                    attempt + 1, self.MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
        self._record_screenshot_path(f"axa_failure_{int(time.time())}.png")
        raise last_exc  # type: ignore[misc]

    def _record_screenshot_path(self, filename: str) -> str:
        path = f"{self.screenshot_dir}/{filename}"
        logger.info("Screenshot would be saved to %s", path)
        return path

    def _parse_portal_response(self, raw: dict[str, Any], policy_number: str, member_id: str) -> CoverageResult:
        status_map = {"Active": "active", "Terminated": "expired", "Suspended": "suspended"}
        member_status = raw.get("member_status", "Unknown")
        mapped = status_map.get(member_status, "unknown")

        overall_limit = raw.get("overall_limit", 0)
        claims_ytd = raw.get("claims_ytd", 0)
        plan_code = raw.get("plan_code", "standard")
        benefits = AXA_PLAN_BENEFITS.get(plan_code, AXA_PLAN_BENEFITS["standard"])

        return CoverageResult(
            policy_number=policy_number,
            member_id=member_id,
            status=mapped,
            plan_type=plan_code,
            annual_limit=overall_limit,
            remaining_balance=round(overall_limit - claims_ytd, 2),
            benefits=benefits,
            raw_response=raw,
        )

    def _do_verify(self, policy_number: str, member_id: str) -> CoverageResult:
        raw = self._retry_with_backoff(_simulated_portal_response, policy_number, member_id)
        return self._parse_portal_response(raw, policy_number, member_id)

    def _do_check_preauth(self, benefit_category: str) -> bool:
        return benefit_category in AXA_PREAUTH_CATEGORIES

    def _do_get_benefits(self, policy_id: str) -> list[dict[str, Any]]:
        plan = "standard"
        if "SEN" in policy_id:
            plan = "senior"
        elif "PREM" in policy_id:
            plan = "premium"
        elif "IND" in policy_id:
            plan = "individual"
        return list(AXA_PLAN_BENEFITS.get(plan, AXA_PLAN_BENEFITS["standard"]))
