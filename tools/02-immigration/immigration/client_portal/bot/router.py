"""Intent detection and message routing for the ClientPortal Bot."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from openclaw_shared.database import get_db

from immigration.client_portal.bot.escalation import should_escalate
from immigration.client_portal.faq.engine import answer_faq
from immigration.client_portal.status.tracker import get_status_display, get_next_steps, lookup_case

logger = logging.getLogger("openclaw.immigration.bot.router")

INTENTS = (
    "status_query",
    "document_question",
    "appointment_request",
    "faq",
    "escalation",
)

INTENT_CLASSIFICATION_PROMPT = """\
You are an intent classifier for an immigration consultancy chatbot in Hong Kong.
Classify the user message into exactly ONE of these intents:
- status_query: asking about case status, progress, or timeline
- document_question: asking about required documents, submission, or deadlines
- appointment_request: wanting to book, reschedule, or cancel a consultation
- faq: general questions about immigration schemes, fees, eligibility, procedures
- escalation: requesting to speak with a human, expressing frustration, complex legal questions

Conversation history (last messages):
{history}

User message: {message}

Respond with ONLY the intent label, nothing else."""

CONTEXT_WINDOW_SIZE = 10


async def handle_incoming_message(
    app_state: Any,
    from_number: str,
    message: str,
    channel: str,
) -> str:
    """Process an incoming client message: classify intent, route, and reply."""
    db = app_state.db_paths["client_portal"]
    llm = app_state.llm
    config = app_state.config

    case = lookup_case(db, phone=from_number)
    case_id = case["id"] if case else None
    lang = case.get("language_pref", "en") if case else "en"

    history = _get_conversation_history(db, case_id)

    _store_message(db, case_id, channel, "client", message)

    intent = await _classify_intent(llm, message, history)
    logger.info("Classified intent=%s for from=%s", intent, from_number)

    if should_escalate(intent, message, history):
        from immigration.client_portal.bot.escalation import escalate_to_consultant
        escalate_to_consultant(case or {"phone": from_number}, history, db)
        response = _escalation_response(lang)
    elif intent == "status_query":
        response = _handle_status_query(case, lang)
    elif intent == "document_question":
        response = _handle_document_question(case, db, lang)
    elif intent == "appointment_request":
        response = _handle_appointment_request(case, lang)
    elif intent == "faq":
        kb_path = config.extra.get("faq_knowledge_base", None)
        response = await _handle_faq(llm, message, lang, kb_path)
    else:
        response = _fallback_response(lang)

    _store_message(db, case_id, channel, "bot", response, intent=intent)

    return response


async def _classify_intent(llm: Any, message: str, history: list[dict]) -> str:
    history_text = "\n".join(
        f"[{m.get('sender', '?')}]: {m.get('message_text', '')}"
        for m in history[-5:]
    ) or "(no prior messages)"

    prompt = INTENT_CLASSIFICATION_PROMPT.format(history=history_text, message=message)

    try:
        result = await llm.complete(prompt, max_tokens=20, temperature=0.0)
        intent = result.strip().lower().replace(" ", "_")
        if intent in INTENTS:
            return intent
    except Exception:
        logger.exception("LLM intent classification failed")

    return "faq"


def _get_conversation_history(db: Any, case_id: int | None) -> list[dict]:
    if case_id is None:
        return []
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT sender, message_text, timestamp FROM conversations "
            "WHERE case_id = ? ORDER BY timestamp DESC LIMIT ?",
            (case_id, CONTEXT_WINDOW_SIZE),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def _store_message(
    db: Any,
    case_id: int | None,
    channel: str,
    sender: str,
    text: str,
    intent: str | None = None,
) -> None:
    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO conversations (case_id, channel, sender, message_text, intent)
               VALUES (?,?,?,?,?)""",
            (case_id, channel, sender, text, intent),
        )


def _handle_status_query(case: dict | None, lang: str) -> str:
    if not case:
        if lang == "zh":
            return "抱歉，我未能找到與您電話號碼相關的個案。請提供您的個案參考編號。"
        return "Sorry, I couldn't find a case linked to your phone number. Could you provide your case reference code?"

    status_label = get_status_display(case["current_status"], lang)
    next_steps = get_next_steps(case["current_status"], case["scheme"], lang)

    if lang == "zh":
        return (
            f"您的個案 {case['reference_code']}（{case['scheme']}）\n"
            f"目前狀態：{status_label}\n\n"
            f"下一步：{next_steps}"
        )
    return (
        f"Your case {case['reference_code']} ({case['scheme']})\n"
        f"Current status: {status_label}\n\n"
        f"Next steps: {next_steps}"
    )


def _handle_document_question(case: dict | None, db: Any, lang: str) -> str:
    if not case:
        if lang == "zh":
            return "請提供您的個案參考編號，以便我查看文件要求。"
        return "Please provide your case reference code so I can check document requirements."

    with get_db(db) as conn:
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM outstanding_documents WHERE case_id = ? AND received = 0 ORDER BY deadline",
            (case["id"],),
        ).fetchall()]

    if not docs:
        if lang == "zh":
            return f"個案 {case['reference_code']} 目前沒有待提交的文件。如有疑問，請聯繫您的顧問。"
        return f"Case {case['reference_code']} has no outstanding documents. Contact your consultant if you have questions."

    if lang == "zh":
        lines = [f"個案 {case['reference_code']} 待提交的文件：\n"]
        for d in docs:
            deadline = d.get("deadline", "未定")
            lines.append(f"• {d['document_type']}（截止日期：{deadline}）")
        return "\n".join(lines)

    lines = [f"Outstanding documents for case {case['reference_code']}:\n"]
    for d in docs:
        deadline = d.get("deadline", "TBD")
        lines.append(f"• {d['document_type']} (deadline: {deadline})")
    return "\n".join(lines)


def _handle_appointment_request(case: dict | None, lang: str) -> str:
    if lang == "zh":
        return (
            "如需預約諮詢，請訪問我們的網上預約系統，或致電辦公室。\n"
            "辦公時間：星期一至五 9:00-18:00，星期六 9:00-13:00"
        )
    return (
        "To book a consultation, please visit our online booking system or call the office.\n"
        "Office hours: Mon-Fri 9:00-18:00, Sat 9:00-13:00"
    )


async def _handle_faq(llm: Any, question: str, lang: str, kb_path: str | None) -> str:
    try:
        from immigration.client_portal.faq.engine import load_knowledge_base
        kb = load_knowledge_base(kb_path)
        answer = await answer_faq(question, llm, kb, lang)
        if answer:
            return answer
    except Exception:
        logger.exception("FAQ engine failed")

    return _fallback_response(lang)


def _escalation_response(lang: str) -> str:
    if lang == "zh":
        return "我將為您轉接顧問。在辦公時間（星期一至五 9:00-18:00，星期六 9:00-13:00），顧問會盡快回覆您。"
    return (
        "I'll connect you with your consultant. During business hours "
        "(Mon-Fri 9am-6pm, Sat 9am-1pm HKT), they'll respond shortly."
    )


def _fallback_response(lang: str) -> str:
    if lang == "zh":
        return "抱歉，我未能理解您的查詢。我將為您轉接顧問以提供進一步協助。"
    return "I'm sorry, I couldn't understand your query. I'll connect you with your consultant for further assistance."
