"""Unified FPS payment interface with abstract bank adapter pattern."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx

from vibe_coder.hk_dev_kit.connectors.fps.fps_types import (
    FPSPaymentRequest,
    FPSPaymentResponse,
)
from vibe_coder.hk_dev_kit.connectors.fps.qr_generator import FPSQRGenerator


class BankAdapter(ABC):
    """Abstract adapter for bank-specific FPS API integration."""

    @abstractmethod
    async def submit_payment(self, request: FPSPaymentRequest) -> dict:
        """Submit a payment request to the bank's FPS endpoint.

        Returns a dict with at least ``transaction_id`` and ``status``.
        """

    @abstractmethod
    async def query_status(self, transaction_id: str) -> str:
        """Query the status of a previously submitted payment."""


class MockBankAdapter(BankAdapter):
    """In-memory adapter for development and testing."""

    def __init__(self) -> None:
        self._transactions: dict[str, dict] = {}

    async def submit_payment(self, request: FPSPaymentRequest) -> dict:
        txn_id = f"FPS-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "transaction_id": txn_id,
            "status": "completed",
            "proxy_id": request.proxy_id,
            "amount": request.amount,
            "currency": request.currency,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self._transactions[txn_id] = record
        return record

    async def query_status(self, transaction_id: str) -> str:
        record = self._transactions.get(transaction_id)
        return record["status"] if record else "not_found"


class HTTPBankAdapter(BankAdapter):
    """Generic HTTP adapter that calls a bank's REST API."""

    def __init__(self, base_url: str, api_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def submit_payment(self, request: FPSPaymentRequest) -> dict:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/fps/payments",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=request.model_dump(),
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json()

    async def query_status(self, transaction_id: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self._base_url}/fps/payments/{transaction_id}",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json().get("status", "unknown")


class FPSPaymentClient:
    """Unified FPS payment interface.

    Uses a pluggable :class:`BankAdapter` for the actual bank communication.
    Defaults to :class:`MockBankAdapter` for local development.
    """

    def __init__(self, adapter: BankAdapter | None = None) -> None:
        self._adapter = adapter or MockBankAdapter()
        self._qr = FPSQRGenerator()

    async def initiate_payment(self, request: FPSPaymentRequest) -> FPSPaymentResponse:
        result = await self._adapter.submit_payment(request)
        qr_data = self._qr.generate(request)
        return FPSPaymentResponse(
            transaction_id=result["transaction_id"],
            status=result["status"],
            qr_data=qr_data,
        )

    async def check_status(self, transaction_id: str) -> str:
        return await self._adapter.query_status(transaction_id)
