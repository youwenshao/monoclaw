"""Octopus card payment Pydantic models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class OctopusPaymentRequest(BaseModel):
    merchant_id: str = Field(..., description="Octopus-assigned merchant identifier")
    amount: float = Field(..., gt=0, description="Payment amount in HKD")
    reference: str = Field(default="", max_length=64, description="Merchant order reference")


class OctopusTransaction(BaseModel):
    transaction_id: str
    status: str = Field(..., description="pending | authorized | completed | refunded | failed")
    amount: float
    timestamp: datetime | None = None


class OctopusRefundRequest(BaseModel):
    transaction_id: str = Field(..., description="Original transaction to refund")
    amount: float = Field(..., gt=0, description="Refund amount (may be partial)")
