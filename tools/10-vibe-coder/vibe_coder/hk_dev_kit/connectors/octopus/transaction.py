"""Octopus transaction query and history management."""

from __future__ import annotations

from datetime import date, datetime, timezone

import httpx

from vibe_coder.hk_dev_kit.connectors.octopus.octopus_types import OctopusTransaction


class TransactionManager:
    """Query historical Octopus merchant transactions."""

    def __init__(
        self,
        base_url: str = "https://api.octopus.com.hk/merchant/v1",
        api_key: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    async def get_history(
        self,
        merchant_id: str,
        start_date: date,
        end_date: date,
    ) -> list[OctopusTransaction]:
        """Fetch transaction history for a merchant within a date range."""
        if not self._api_key:
            return self._mock_history(merchant_id, start_date, end_date)

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/merchants/{merchant_id}/transactions",
                headers=self._headers(),
                params={
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            OctopusTransaction(
                transaction_id=item["transaction_id"],
                status=item["status"],
                amount=item["amount"],
                timestamp=datetime.fromisoformat(item["timestamp"]) if item.get("timestamp") else None,
            )
            for item in data.get("transactions", [])
        ]

    def _mock_history(
        self,
        merchant_id: str,
        start_date: date,
        end_date: date,
    ) -> list[OctopusTransaction]:
        now = datetime.now(timezone.utc)
        return [
            OctopusTransaction(
                transaction_id=f"OCT-HIST-{i:04d}",
                status="completed",
                amount=50.0 + i * 10,
                timestamp=now,
            )
            for i in range(1, 4)
        ]
