"""Abstract base connector for insurance portal verification."""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.insurance.verification")


class CoverageResult:
    """Structured result from an insurance coverage verification."""

    __slots__ = (
        "policy_number", "member_id", "status", "plan_type",
        "annual_limit", "remaining_balance", "benefits",
        "verified_at", "raw_response", "error",
    )

    def __init__(
        self,
        *,
        policy_number: str = "",
        member_id: str = "",
        status: str = "unknown",
        plan_type: str = "",
        annual_limit: float = 0.0,
        remaining_balance: float = 0.0,
        benefits: list[dict[str, Any]] | None = None,
        verified_at: float | None = None,
        raw_response: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.policy_number = policy_number
        self.member_id = member_id
        self.status = status
        self.plan_type = plan_type
        self.annual_limit = annual_limit
        self.remaining_balance = remaining_balance
        self.benefits = benefits or []
        self.verified_at = verified_at or time.time()
        self.raw_response = raw_response or {}
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy_number": self.policy_number,
            "member_id": self.member_id,
            "status": self.status,
            "plan_type": self.plan_type,
            "annual_limit": self.annual_limit,
            "remaining_balance": self.remaining_balance,
            "benefits": self.benefits,
            "verified_at": self.verified_at,
            "error": self.error,
        }


class GenericConnector(ABC):
    """Abstract base class for insurance portal connectors.

    Provides 24-hour result caching and configurable rate limiting.
    Concrete subclasses implement the portal-specific verification logic.
    """

    CACHE_TTL: float = 86400.0  # 24 hours

    def __init__(
        self,
        insurer_name: str,
        portal_url: str = "",
        rate_limit_seconds: float = 2.0,
        screenshot_dir: str = "",
    ) -> None:
        self.insurer_name = insurer_name
        self.portal_url = portal_url
        self.rate_limit_seconds = rate_limit_seconds
        self.screenshot_dir = screenshot_dir
        self._cache: dict[str, tuple[float, dict[str, Any]]] = {}
        self._last_request_time: float = 0.0

    # -- Rate limiting ---------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit_seconds:
            time.sleep(self.rate_limit_seconds - elapsed)
        self._last_request_time = time.time()

    # -- Caching ---------------------------------------------------------------

    def _cache_key(self, policy_number: str, member_id: str) -> str:
        return f"{self.insurer_name}:{policy_number}:{member_id}"

    def _get_cached(self, key: str) -> dict[str, Any] | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, result = entry
        if time.time() - timestamp > self.CACHE_TTL:
            del self._cache[key]
            return None
        return result

    def _set_cached(self, key: str, result: dict[str, Any]) -> None:
        self._cache[key] = (time.time(), result)

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- Public API ------------------------------------------------------------

    def verify_coverage(self, policy_number: str, member_id: str) -> dict[str, Any]:
        """Verify insurance coverage for a policy/member.

        Returns a dict with keys: policy_number, member_id, status, plan_type,
        annual_limit, remaining_balance, benefits, verified_at, error.
        Results are cached for 24 hours.
        """
        cache_key = self._cache_key(policy_number, member_id)
        cached = self._get_cached(cache_key)
        if cached is not None:
            logger.debug("Cache hit for %s", cache_key)
            return cached

        self._wait_for_rate_limit()

        try:
            result = self._do_verify(policy_number, member_id)
        except Exception as exc:
            logger.error("Verification failed for %s: %s", cache_key, exc)
            result = CoverageResult(
                policy_number=policy_number,
                member_id=member_id,
                status="error",
                error=str(exc),
            )

        result_dict = result.to_dict()
        self._set_cached(cache_key, result_dict)
        return result_dict

    def check_preauth_required(self, benefit_category: str) -> bool:
        """Check whether a benefit category requires pre-authorization."""
        return self._do_check_preauth(benefit_category)

    def get_benefits(self, policy_id: str) -> list[dict[str, Any]]:
        """Return the list of benefit categories and limits for a policy."""
        self._wait_for_rate_limit()
        return self._do_get_benefits(policy_id)

    # -- Abstract methods for subclasses ---------------------------------------

    @abstractmethod
    def _do_verify(self, policy_number: str, member_id: str) -> CoverageResult:
        """Portal-specific verification logic."""
        ...

    @abstractmethod
    def _do_check_preauth(self, benefit_category: str) -> bool:
        """Portal-specific pre-auth check."""
        ...

    @abstractmethod
    def _do_get_benefits(self, policy_id: str) -> list[dict[str, Any]]:
        """Portal-specific benefits lookup."""
        ...
