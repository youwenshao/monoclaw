"""Bilingual (EN/TC) message templates for the MedReminder bot.

Templates follow HK Department of Health drug labelling format:
drug name, strength, dosage, route, frequency.
"""

from __future__ import annotations


def reminder_message(
    med_name_en: str,
    med_name_tc: str,
    dosage: str,
    frequency: str,
    language: str,
) -> str:
    """Build a medication reminder message in the patient's preferred language."""
    if language in ("tc", "zh"):
        return (
            f"💊 食藥提醒\n"
            f"藥名：{med_name_tc}（{med_name_en}）\n"
            f"劑量：{dosage}\n"
            f"服法：{frequency}\n\n"
            f"請服藥後回覆「已服」確認。\n"
            f"如需補藥，請回覆「補藥」或拍攝藥物包裝照片。"
        )
    return (
        f"💊 Medication Reminder\n"
        f"Drug: {med_name_en} ({med_name_tc})\n"
        f"Dosage: {dosage}\n"
        f"Frequency: {frequency}\n\n"
        f'Please reply "taken" to confirm.\n'
        f'For refills, reply "refill" or send a photo of the packaging.'
    )


def refill_confirmation(
    med_name: str,
    status: str,
    language: str,
) -> str:
    """Build a refill status update message."""
    status_map_tc: dict[str, str] = {
        "pending": "處理中",
        "approved": "已批准",
        "modified": "已批准（藥物已調整）",
        "rejected": "未獲批准",
        "ready": "已備妥，請到診所領取",
        "collected": "已領取",
    }
    status_map_en: dict[str, str] = {
        "pending": "Pending review",
        "approved": "Approved",
        "modified": "Approved (medication adjusted)",
        "rejected": "Not approved",
        "ready": "Ready for collection at the clinic",
        "collected": "Collected",
    }

    if language in ("tc", "zh"):
        return (
            f"📋 補藥申請更新\n"
            f"藥名：{med_name}\n"
            f"狀態：{status_map_tc.get(status, status)}"
        )
    return (
        f"📋 Refill Request Update\n"
        f"Drug: {med_name}\n"
        f"Status: {status_map_en.get(status, status)}"
    )


def compliance_warning(
    patient_name: str,
    rate: float,
    language: str,
) -> str:
    """Build a low-compliance alert message for clinic staff or patient."""
    pct = f"{rate:.0f}%"
    if language in ("tc", "zh"):
        return (
            f"⚠️ 服藥依從性提醒\n"
            f"病人：{patient_name}\n"
            f"過去30天依從率：{pct}\n\n"
            f"請按時服藥。如有困難，請聯絡診所查詢。"
        )
    return (
        f"⚠️ Compliance Alert\n"
        f"Patient: {patient_name}\n"
        f"30-day compliance rate: {pct}\n\n"
        f"Please take your medication on time. "
        f"Contact the clinic if you need assistance."
    )


def taken_confirmation(language: str) -> str:
    """Acknowledge a "taken" response."""
    if language in ("tc", "zh"):
        return "✅ 已記錄。請繼續按時服藥！"
    return "✅ Recorded. Keep up the good work!"


def refill_request_received(language: str) -> str:
    """Acknowledge that a refill request was received."""
    if language in ("tc", "zh"):
        return "📥 補藥申請已收到，診所會盡快處理。"
    return "📥 Refill request received. The clinic will process it shortly."


def photo_received(language: str) -> str:
    """Acknowledge a photo submission."""
    if language in ("tc", "zh"):
        return "📸 已收到照片，正在處理補藥申請⋯⋯"
    return "📸 Photo received. Processing your refill request..."


def unknown_message(language: str) -> str:
    """Response for unrecognised messages."""
    if language in ("tc", "zh"):
        return (
            "抱歉，我未能理解您的訊息。\n"
            "您可以回覆：\n"
            "• 「已服」— 確認已服藥\n"
            "• 「補藥」— 申請補藥\n"
            "• 拍攝藥物照片 — 申請補藥"
        )
    return (
        "Sorry, I didn't understand your message.\n"
        "You can reply with:\n"
        '• "taken" — confirm medication taken\n'
        '• "refill" — request a refill\n'
        "• Send a photo of your medication packaging"
    )
