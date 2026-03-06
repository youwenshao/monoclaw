"""FPS (Faster Payment System) Pydantic models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FPSProxyType(str, Enum):
    MOBILE = "mobile"
    FPS_ID = "fps_id"
    EMAIL = "email"
    BR_NUMBER = "br_number"


class FPSPaymentRequest(BaseModel):
    proxy_id: str = Field(..., description="Recipient identifier (phone, FPS ID, email, or BR)")
    proxy_type: FPSProxyType
    amount: float = Field(..., gt=0, description="Payment amount")
    currency: str = Field(default="HKD", pattern=r"^[A-Z]{3}$")
    reference: str = Field(default="", max_length=35, description="Payment reference / memo")


class FPSPaymentResponse(BaseModel):
    transaction_id: str
    status: str = Field(..., description="pending | completed | failed")
    qr_data: bytes | None = Field(default=None, description="QR code PNG bytes when applicable")
