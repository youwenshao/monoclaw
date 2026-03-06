"""Notification message formatting for tenancy renewal reminders."""

from __future__ import annotations


def format_renewal_reminder(
    tenancy: dict,
    days_remaining: int,
    language: str = "en",
) -> str:
    """Return a formatted renewal reminder message.

    Parameters
    ----------
    tenancy:
        Tenancy row dict (must have ``property_address``, ``tenant_name``,
        ``landlord_name``, ``end_date``, ``monthly_rent``).
    days_remaining:
        Days until the tenancy expires.
    language:
        ``"en"`` for English, ``"zh"`` for Traditional Chinese,
        ``"both"`` for bilingual.
    """
    address = tenancy.get("property_address", "N/A")
    address_zh = tenancy.get("property_address_zh", address)
    tenant = tenancy.get("tenant_name", "N/A")
    landlord = tenancy.get("landlord_name", "N/A")
    end_date = tenancy.get("end_date", "N/A")
    rent = tenancy.get("monthly_rent", 0)

    urgency = _urgency_label(days_remaining, language)

    if language == "zh":
        return (
            f"{urgency}\n"
            f"物業: {address_zh}\n"
            f"租客: {tenant}\n"
            f"業主: {landlord}\n"
            f"到期日: {end_date}\n"
            f"每月租金: HK${rent:,}\n"
            f"剩餘日數: {days_remaining} 天\n\n"
            f"請儘快安排續約或退租事宜。"
        )

    en_msg = (
        f"{urgency}\n"
        f"Property: {address}\n"
        f"Tenant: {tenant}\n"
        f"Landlord: {landlord}\n"
        f"Expiry: {end_date}\n"
        f"Monthly Rent: HK${rent:,}\n"
        f"Days Remaining: {days_remaining}\n\n"
        f"Please arrange renewal or handover accordingly."
    )

    if language == "both":
        zh_msg = format_renewal_reminder(tenancy, days_remaining, "zh")
        return f"{en_msg}\n\n{'─' * 40}\n\n{zh_msg}"

    return en_msg


def _urgency_label(days: int, language: str) -> str:
    if language == "zh":
        if days <= 14:
            return "🔴 緊急租約續期提醒"
        if days <= 30:
            return "🟠 租約續期提醒"
        if days <= 60:
            return "🟡 租約續期通知"
        return "🟢 租約到期預告"

    if days <= 14:
        return "🔴 URGENT RENEWAL REMINDER"
    if days <= 30:
        return "🟠 RENEWAL REMINDER"
    if days <= 60:
        return "🟡 RENEWAL NOTICE"
    return "🟢 RENEWAL HEADS-UP"
