"""Octopus merchant payment client implementing tap-authorize-confirm flow.

Octopus O!ePay / merchant integration follows a three-phase model:
1. **Tap** — customer taps Octopus card on the reader / scans QR.
2. **Authorize** — the Octopus backend authorizes the stored-value deduction.
3. **Confirm** — merchant confirms the deduction and settles the transaction.

This client abstracts those phases behind a single ``create_payment`` call and
provides query/refund capabilities.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx

from vibe_coder.hk_dev_kit.connectors.octopus.octopus_types import (
    OctopusPaymentRequest,
    OctopusRefundRequest,
    OctopusTransaction,
)


class OctopusMerchantClient:
    """Async client for the Octopus merchant payment API."""

    def __init__(
        self,
        base_url: str = "https://api.octopus.com.hk/merchant/v1",
        api_key: str = "",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._local_store: dict[str, OctopusTransaction] = {}

    def _headers(self) -> dict[str, str]:
        return {
            "X-Api-Key": self._api_key,
            "Content-Type": "application/json",
        }

    async def create_payment(self, request: OctopusPaymentRequest) -> OctopusTransaction:
        """Execute tap-authorize-confirm flow and return the completed transaction."""
        if not self._api_key:
            return self._mock_payment(request)

        async with httpx.AsyncClient() as client:
            # Phase 1+2: initiate tap and authorize
            resp = await client.post(
                f"{self._base_url}/payments",
                headers=self._headers(),
                json={
                    "merchant_id": request.merchant_id,
                    "amount": request.amount,
                    "reference": request.reference,
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            txn_id = data["transaction_id"]

            # Phase 3: confirm
            confirm_resp = await client.post(
                f"{self._base_url}/payments/{txn_id}/confirm",
                headers=self._headers(),
                timeout=15,
            )
            confirm_resp.raise_for_status()
            confirmed = confirm_resp.json()

        return OctopusTransaction(
            transaction_id=txn_id,
            status=confirmed.get("status", "completed"),
            amount=request.amount,
            timestamp=datetime.now(timezone.utc),
        )

    async def query_transaction(self, transaction_id: str) -> OctopusTransaction:
        if not self._api_key:
            return self._local_store.get(
                transaction_id,
                OctopusTransaction(
                    transaction_id=transaction_id,
                    status="not_found",
                    amount=0,
                ),
            )

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/payments/{transaction_id}",
                headers=self._headers(),
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

        return OctopusTransaction(
            transaction_id=data["transaction_id"],
            status=data["status"],
            amount=data["amount"],
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else None,
        )

    async def refund(self, request: OctopusRefundRequest) -> OctopusTransaction:
        if not self._api_key:
            return self._mock_refund(request)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/payments/{request.transaction_id}/refund",
                headers=self._headers(),
                json={"amount": request.amount},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()

        return OctopusTransaction(
            transaction_id=data["transaction_id"],
            status="refunded",
            amount=request.amount,
            timestamp=datetime.now(timezone.utc),
        )

    # -- Mock helpers for local dev -------------------------------------------

    def _mock_payment(self, request: OctopusPaymentRequest) -> OctopusTransaction:
        txn_id = f"OCT-{uuid.uuid4().hex[:8].upper()}"
        txn = OctopusTransaction(
            transaction_id=txn_id,
            status="completed",
            amount=request.amount,
            timestamp=datetime.now(timezone.utc),
        )
        self._local_store[txn_id] = txn
        return txn

    def _mock_refund(self, request: OctopusRefundRequest) -> OctopusTransaction:
        txn_id = f"OCT-R-{uuid.uuid4().hex[:8].upper()}"
        txn = OctopusTransaction(
            transaction_id=txn_id,
            status="refunded",
            amount=request.amount,
            timestamp=datetime.now(timezone.utc),
        )
        self._local_store[txn_id] = txn
        return txn
