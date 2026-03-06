"""China fapiao (增值稅發票 / VAT invoice) parser.

Handles the standardised government format used for Chinese VAT invoices,
extracting the key fields mandated by the State Taxation Administration.
"""

from __future__ import annotations

import re
from typing import Any


_FAPIAO_CODE_PATTERN = re.compile(
    r"(?:發票代碼|发票代码|Invoice\s*Code)\s*[：:]\s*(\d{10,12})",
    re.IGNORECASE,
)
_FAPIAO_NUM_PATTERN = re.compile(
    r"(?:發票號碼|发票号码|Invoice\s*No\.?)\s*[：:]\s*(\d{8})",
    re.IGNORECASE,
)
_FAPIAO_DATE_PATTERN = re.compile(
    r"(?:開票日期|开票日期|Date)\s*[：:]\s*(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日|\d{4}[-/]\d{1,2}[-/]\d{1,2})",
    re.IGNORECASE,
)
_BUYER_PATTERN = re.compile(
    r"(?:購買方|购买方|Buyer|購方名稱|购方名称)\s*[：:]?\s*(.+)",
    re.IGNORECASE,
)
_SELLER_PATTERN = re.compile(
    r"(?:銷售方|销售方|Seller|銷方名稱|销方名称)\s*[：:]?\s*(.+)",
    re.IGNORECASE,
)
_AMOUNT_PATTERN = re.compile(r"([\d,]+\.\d{2})")
_TAX_AMOUNT_PATTERN = re.compile(
    r"(?:稅額|税额|Tax\s*Amount)\s*[：:]?\s*[¥￥]?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_TOTAL_PATTERN = re.compile(
    r"(?:價稅合計|价税合计|Total)\s*[：:]?\s*[¥￥]?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_PRETAX_PATTERN = re.compile(
    r"(?:金額|金额|Amount)\s*[：:]?\s*[¥￥]?\s*([\d,]+\.\d{2})",
    re.IGNORECASE,
)
_BUYER_TIN_PATTERN = re.compile(
    r"(?:購買方.*?納稅人識別號|购买方.*?纳税人识别号|Buyer.*?TIN)\s*[：:]\s*([\dA-Z]{15,20})",
    re.IGNORECASE,
)
_SELLER_TIN_PATTERN = re.compile(
    r"(?:銷售方.*?納稅人識別號|销售方.*?纳税人识别号|Seller.*?TIN)\s*[：:]\s*([\dA-Z]{15,20})",
    re.IGNORECASE,
)
_CHECKCODE_PATTERN = re.compile(
    r"(?:校驗碼|校验码|Check\s*Code)\s*[：:]\s*([\d\s]{20,})",
    re.IGNORECASE,
)


def _normalize_date(raw: str) -> str:
    """Convert Chinese-style date (2026年3月1日) to ISO format."""
    m = re.match(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return raw.strip()


def _parse_amount(text: str) -> float | None:
    m = _AMOUNT_PATTERN.search(text)
    if m:
        try:
            return float(m.group(1).replace(",", ""))
        except ValueError:
            pass
    return None


def parse_fapiao(ocr_result: dict[str, Any]) -> dict[str, Any]:
    """Parse a Chinese VAT fapiao from OCR output.

    Returns dict with:
        發票代碼 (fapiao_code), 發票號碼 (fapiao_number),
        開票日期 (issue_date), 購買方 (buyer), 銷售方 (seller),
        金額 (pretax_amount), 稅額 (tax_amount), 價稅合計 (total_amount),
        buyer_tin, seller_tin, check_code, currency.
    """
    raw_text = ocr_result.get("raw_text", "")

    result: dict[str, Any] = {
        "fapiao_code": None,
        "fapiao_number": None,
        "issue_date": None,
        "buyer": None,
        "seller": None,
        "buyer_tin": None,
        "seller_tin": None,
        "pretax_amount": None,
        "tax_amount": None,
        "total_amount": None,
        "check_code": None,
        "currency": "CNY",
    }

    m = _FAPIAO_CODE_PATTERN.search(raw_text)
    if m:
        result["fapiao_code"] = m.group(1).strip()

    m = _FAPIAO_NUM_PATTERN.search(raw_text)
    if m:
        result["fapiao_number"] = m.group(1).strip()

    m = _FAPIAO_DATE_PATTERN.search(raw_text)
    if m:
        result["issue_date"] = _normalize_date(m.group(1))

    m = _BUYER_PATTERN.search(raw_text)
    if m:
        result["buyer"] = m.group(1).strip().rstrip("：:")

    m = _SELLER_PATTERN.search(raw_text)
    if m:
        result["seller"] = m.group(1).strip().rstrip("：:")

    m = _BUYER_TIN_PATTERN.search(raw_text)
    if m:
        result["buyer_tin"] = m.group(1).strip()

    m = _SELLER_TIN_PATTERN.search(raw_text)
    if m:
        result["seller_tin"] = m.group(1).strip()

    m = _PRETAX_PATTERN.search(raw_text)
    if m:
        result["pretax_amount"] = _parse_amount(m.group(0))

    m = _TAX_AMOUNT_PATTERN.search(raw_text)
    if m:
        result["tax_amount"] = _parse_amount(m.group(0))

    m = _TOTAL_PATTERN.search(raw_text)
    if m:
        result["total_amount"] = _parse_amount(m.group(0))

    if result["total_amount"] is None and result["pretax_amount"] is not None:
        tax = result["tax_amount"] or 0.0
        result["total_amount"] = round(result["pretax_amount"] + tax, 2)

    m = _CHECKCODE_PATTERN.search(raw_text)
    if m:
        result["check_code"] = m.group(1).replace(" ", "").strip()

    return result
