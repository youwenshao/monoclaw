"""EMV QR code generation per HKMA FPS specification.

Builds an EMV-format payload string conforming to the EMVCo QR Code
Specification for Payment Systems (Merchant-Presented Mode) as adopted by
HKMA for the Faster Payment System.
"""

from __future__ import annotations

from io import BytesIO

import qrcode
from qrcode.constants import ERROR_CORRECT_M

from vibe_coder.hk_dev_kit.connectors.fps.fps_types import FPSPaymentRequest, FPSProxyType

_PROXY_TYPE_TAG = {
    FPSProxyType.MOBILE: "01",
    FPSProxyType.FPS_ID: "02",
    FPSProxyType.EMAIL: "03",
    FPSProxyType.BR_NUMBER: "04",
}

_FPS_GUID = "hk.com.hkicl"
_CURRENCY_CODE_HKD = "344"
_COUNTRY_CODE = "HK"


def _tlv(tag: str, value: str) -> str:
    """Build a TLV (tag-length-value) element for the EMV payload."""
    length = f"{len(value):02d}"
    return f"{tag}{length}{value}"


def _crc16_ccitt(data: bytes) -> str:
    """CRC-16/CCITT-FALSE used by EMVCo QR payloads."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = (crc << 1) ^ 0x1021
            else:
                crc <<= 1
            crc &= 0xFFFF
    return f"{crc:04X}"


class FPSQRGenerator:
    """Generate EMV-format FPS QR codes as PNG images."""

    def generate(self, payment: FPSPaymentRequest) -> bytes:
        """Return PNG image bytes of an EMV-format FPS QR code."""
        payload = self._build_payload(payment)
        return self._render_qr(payload)

    def _build_payload(self, payment: FPSPaymentRequest) -> str:
        parts: list[str] = []

        # ID 00 – Payload Format Indicator
        parts.append(_tlv("00", "01"))

        # ID 01 – Point of Initiation Method (12 = dynamic)
        parts.append(_tlv("01", "12"))

        # ID 26 – Merchant Account Information (FPS-specific)
        proxy_tag = _PROXY_TYPE_TAG[payment.proxy_type]
        merchant_inner = (
            _tlv("00", _FPS_GUID)
            + _tlv("01", proxy_tag)
            + _tlv("02", payment.proxy_id)
        )
        parts.append(_tlv("26", merchant_inner))

        # ID 52 – Merchant Category Code (0000 = not applicable)
        parts.append(_tlv("52", "0000"))

        # ID 53 – Transaction Currency (344 = HKD)
        currency_code = _CURRENCY_CODE_HKD if payment.currency == "HKD" else "840"
        parts.append(_tlv("53", currency_code))

        # ID 54 – Transaction Amount
        amount_str = f"{payment.amount:.2f}"
        parts.append(_tlv("54", amount_str))

        # ID 58 – Country Code
        parts.append(_tlv("58", _COUNTRY_CODE))

        # ID 62 – Additional Data Field Template
        if payment.reference:
            additional = _tlv("05", payment.reference)
            parts.append(_tlv("62", additional))

        # ID 63 – CRC (placeholder then compute)
        raw = "".join(parts) + "6304"
        crc = _crc16_ccitt(raw.encode("ascii"))
        payload = raw + crc

        return payload

    def _render_qr(self, data: str) -> bytes:
        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
