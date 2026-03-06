"""Case status management for the ClientPortal Bot."""

from __future__ import annotations

from typing import Any

from openclaw_shared.database import get_db

VALID_STATUSES = [
    "documents_gathering",
    "application_submitted",
    "acknowledgement_received",
    "additional_documents_requested",
    "under_processing",
    "approval_in_principle",
    "visa_label_issued",
    "entry_made",
    "hkid_applied",
]

STATUS_LABELS: dict[str, dict[str, str]] = {
    "documents_gathering": {
        "en": "Gathering Documents",
        "zh": "收集文件中",
    },
    "application_submitted": {
        "en": "Application Submitted",
        "zh": "申請已提交",
    },
    "acknowledgement_received": {
        "en": "Acknowledgement Received",
        "zh": "已收到確認書",
    },
    "additional_documents_requested": {
        "en": "Additional Documents Requested",
        "zh": "需要補充文件",
    },
    "under_processing": {
        "en": "Under Processing",
        "zh": "審核中",
    },
    "approval_in_principle": {
        "en": "Approval in Principle",
        "zh": "原則上批准",
    },
    "visa_label_issued": {
        "en": "Visa Label Issued",
        "zh": "簽證標籤已發出",
    },
    "entry_made": {
        "en": "Entry to Hong Kong Made",
        "zh": "已入境香港",
    },
    "hkid_applied": {
        "en": "HKID Application Submitted",
        "zh": "已申請香港身份證",
    },
}

NEXT_STEPS: dict[str, dict[str, str]] = {
    "documents_gathering": {
        "en": "Please prepare and submit all required documents before the deadline. "
              "Check your outstanding documents list for details.",
        "zh": "請在截止日期前準備及提交所有所需文件。請查看您的待提交文件清單了解詳情。",
    },
    "application_submitted": {
        "en": "Your application has been submitted to the Immigration Department. "
              "You will receive an acknowledgement letter within 2-4 weeks.",
        "zh": "您的申請已提交至入境事務處。您將在2至4星期內收到確認函。",
    },
    "acknowledgement_received": {
        "en": "ImmD has acknowledged your application. Processing has begun. "
              "We will notify you of any updates or requests for additional documents.",
        "zh": "入境處已確認收到您的申請。審批程序已開始。如有更新或需補充文件，我們會通知您。",
    },
    "additional_documents_requested": {
        "en": "The Immigration Department has requested additional documents. "
              "Please submit the requested items as soon as possible to avoid delays.",
        "zh": "入境處要求提交補充文件。請盡快提交所需文件以避免延誤。",
    },
    "under_processing": {
        "en": "Your application is being processed by the Immigration Department. "
              "This typically takes {scheme_time}. We'll keep you updated.",
        "zh": "您的申請正由入境處審批中。通常需要{scheme_time}。我們會持續通知您最新情況。",
    },
    "approval_in_principle": {
        "en": "Congratulations! Your application has been approved in principle. "
              "Please arrange to collect your visa label or have it posted.",
        "zh": "恭喜！您的申請已獲原則性批准。請安排領取簽證標籤或選擇郵寄方式。",
    },
    "visa_label_issued": {
        "en": "Your visa label has been issued. Please enter Hong Kong within the validity period "
              "and register for an HKID within 30 days of arrival.",
        "zh": "您的簽證標籤已發出。請在有效期內入境香港，並在抵港後30天內申請香港身份證。",
    },
    "entry_made": {
        "en": "Welcome to Hong Kong! Please apply for your HKID card within 30 days at any "
              "Registration of Persons Office.",
        "zh": "歡迎來到香港！請在30天內到任何人事登記辦事處申請香港身份證。",
    },
    "hkid_applied": {
        "en": "Your HKID application is being processed. You will be notified when your card "
              "is ready for collection. Keep your acknowledgement slip safe.",
        "zh": "您的身份證申請正在處理中。身份證可領取時會通知您。請妥善保管回條。",
    },
}

SCHEME_PROCESSING_TIMES: dict[str, str] = {
    "GEP": "4-6 weeks",
    "ASMTP": "4-6 weeks",
    "QMAS": "9-12 months",
    "TTPS": "about 4 weeks",
    "IANG": "2-4 weeks",
    "Dependant": "4-6 weeks",
}

SCHEME_PROCESSING_TIMES_ZH: dict[str, str] = {
    "GEP": "4至6星期",
    "ASMTP": "4至6星期",
    "QMAS": "9至12個月",
    "TTPS": "約4星期",
    "IANG": "2至4星期",
    "Dependant": "4至6星期",
}


def get_status_display(status: str, lang: str = "en") -> str:
    """Return a human-readable label for the given status code."""
    labels = STATUS_LABELS.get(status, {})
    return labels.get(lang, labels.get("en", status.replace("_", " ").title()))


def get_next_steps(status: str, scheme: str, lang: str = "en") -> str:
    """Return next-step guidance for the given status and visa scheme."""
    steps = NEXT_STEPS.get(status, {})
    text = steps.get(lang, steps.get("en", "Please contact your consultant for guidance."))

    if "{scheme_time}" in text:
        times = SCHEME_PROCESSING_TIMES_ZH if lang == "zh" else SCHEME_PROCESSING_TIMES
        scheme_time = times.get(scheme, "several weeks" if lang == "en" else "數星期")
        text = text.replace("{scheme_time}", scheme_time)

    return text


def lookup_case(
    db_path: Any,
    reference_code: str | None = None,
    phone: str | None = None,
) -> dict | None:
    """Look up a case by reference code or client phone number."""
    with get_db(db_path) as conn:
        if reference_code:
            row = conn.execute(
                "SELECT * FROM cases WHERE reference_code = ?",
                (reference_code,),
            ).fetchone()
            if row:
                return dict(row)

        if phone:
            row = conn.execute(
                "SELECT * FROM cases WHERE client_phone = ? ORDER BY created_at DESC LIMIT 1",
                (phone,),
            ).fetchone()
            if row:
                return dict(row)

    return None
