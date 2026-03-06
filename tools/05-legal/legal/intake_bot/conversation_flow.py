"""State machine for guided client intake conversations."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any


class State(str, Enum):
    GREETING = "GREETING"
    COLLECT_NAME = "COLLECT_NAME"
    COLLECT_CONTACT = "COLLECT_CONTACT"
    COLLECT_MATTER = "COLLECT_MATTER"
    COLLECT_ADVERSE_PARTY = "COLLECT_ADVERSE_PARTY"
    CONFIRM = "CONFIRM"
    COMPLETE = "COMPLETE"
    HUMAN_ESCALATION = "HUMAN_ESCALATION"


_ESCALATION_TRIGGERS = re.compile(
    r"\b(speak to (a |)human|talk to (a |)lawyer|real person|transfer|operator|help me|"
    r"connect me|solicitor please|legal advice)\b",
    re.IGNORECASE,
)

_GREETING_RESPONSES = [
    "Hello! I'm the intake assistant for our law firm. I'll help you get started.",
    "May I have your full name, please? If you have a Chinese name, "
    "please provide both English and Chinese versions separated by a slash.\n"
    "Example: Chan Tai Man / 陳大文",
]

_MATTER_TYPES = [
    "contract_dispute",
    "personal_injury",
    "tenancy_dispute",
    "corporate",
    "employment",
    "family",
    "criminal",
    "immigration",
    "other",
]


class IntakeConversation:
    """Stateful conversation handler for client intake.

    Each conversation instance tracks one client through the intake flow.
    """

    def __init__(self, language: str = "en") -> None:
        self._state = State.GREETING
        self._data: dict[str, Any] = {}
        self._language = language
        self._step_within_state = 0

    def get_state(self) -> str:
        return self._state.value

    def get_collected_data(self) -> dict[str, Any]:
        return dict(self._data)

    def process_message(self, message: str) -> str:
        """Process an incoming message, advance state, return a response."""
        text = message.strip()

        if _ESCALATION_TRIGGERS.search(text):
            self._state = State.HUMAN_ESCALATION
            return (
                "I understand you'd like to speak with a solicitor directly. "
                "I'm transferring you to our team now. A member of staff will "
                "be with you shortly. Thank you for your patience."
            )

        handler = _STATE_HANDLERS.get(self._state, _handle_complete)
        response, next_state = handler(self, text)
        if next_state != self._state:
            self._step_within_state = 0
        self._state = next_state
        return response


# ---------------------------------------------------------------------------
# State handler functions
# ---------------------------------------------------------------------------

def _handle_greeting(conv: IntakeConversation, _message: str) -> tuple[str, State]:
    return (
        "\n".join(_GREETING_RESPONSES),
        State.COLLECT_NAME,
    )


def _handle_collect_name(conv: IntakeConversation, message: str) -> tuple[str, State]:
    if not message:
        return ("Please enter your full name to continue.", State.COLLECT_NAME)

    if "/" in message:
        parts = [p.strip() for p in message.split("/", 1)]
        conv._data["name_en"] = parts[0]
        conv._data["name_tc"] = parts[1]
    else:
        conv._data["name_en"] = message
        conv._data["name_tc"] = ""

    return (
        f"Thank you, {conv._data['name_en']}. "
        "Now I need your contact details.\n"
        "Please provide your phone number (HK format, e.g. +85291234567):",
        State.COLLECT_CONTACT,
    )


def _handle_collect_contact(conv: IntakeConversation, message: str) -> tuple[str, State]:
    step = conv._step_within_state

    if step == 0 or "phone" not in conv._data:
        phone = re.sub(r"[\s\-()]", "", message)
        if not re.match(r"^\+?852\d{8}$", phone) and not re.match(r"^\d{8}$", message.replace(" ", "")):
            return (
                "That doesn't look like a valid HK phone number. "
                "Please enter an 8-digit number (with optional +852 prefix):",
                State.COLLECT_CONTACT,
            )
        if not phone.startswith("+"):
            phone = "+852" + phone.lstrip("852").lstrip("+")
        conv._data["phone"] = phone
        conv._step_within_state = 1
        return (
            "Got it. What is your email address? (Type 'skip' if you'd prefer not to share)",
            State.COLLECT_CONTACT,
        )

    email = message.strip().lower()
    if email == "skip" or email == "none":
        conv._data["email"] = None
    elif re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        conv._data["email"] = email
    else:
        return (
            "That doesn't look like a valid email. Please try again or type 'skip':",
            State.COLLECT_CONTACT,
        )

    matter_list = "\n".join(f"  {i+1}. {t.replace('_', ' ').title()}" for i, t in enumerate(_MATTER_TYPES))
    return (
        "Thank you. What type of legal matter do you need help with?\n"
        f"{matter_list}\n\n"
        "Please enter the number or describe your issue:",
        State.COLLECT_MATTER,
    )


def _handle_collect_matter(conv: IntakeConversation, message: str) -> tuple[str, State]:
    step = conv._step_within_state

    if step == 0 or "matter_type" not in conv._data:
        stripped = message.strip()

        if stripped.isdigit():
            idx = int(stripped) - 1
            if 0 <= idx < len(_MATTER_TYPES):
                conv._data["matter_type"] = _MATTER_TYPES[idx]
            else:
                return (
                    f"Please enter a number between 1 and {len(_MATTER_TYPES)}:",
                    State.COLLECT_MATTER,
                )
        else:
            lower = stripped.lower().replace(" ", "_")
            if lower in _MATTER_TYPES:
                conv._data["matter_type"] = lower
            else:
                conv._data["matter_type"] = "other"
                conv._data["matter_description"] = stripped

        conv._step_within_state = 1
        return (
            "Please briefly describe your situation:",
            State.COLLECT_MATTER,
        )

    conv._data["matter_description"] = message.strip()
    conv._step_within_state = 2

    urgency_prompt = (
        "How urgent is this matter?\n"
        "  1. Urgent (court deadlines, time-sensitive)\n"
        "  2. Normal\n"
        "  3. Low priority\n"
        "Please enter a number:"
    )
    return (urgency_prompt, State.COLLECT_MATTER)


def _handle_collect_matter_urgency(conv: IntakeConversation, message: str) -> tuple[str, State]:
    """Sub-handler for urgency within COLLECT_MATTER (step 2)."""
    urgency_map = {"1": "urgent", "2": "normal", "3": "low"}
    choice = message.strip()
    conv._data["urgency"] = urgency_map.get(choice, "normal")

    return (
        "Is there an adverse party (the other side) in this matter? "
        "If yes, please provide their name. If not, type 'none':",
        State.COLLECT_ADVERSE_PARTY,
    )


def _handle_collect_adverse_party(conv: IntakeConversation, message: str) -> tuple[str, State]:
    text = message.strip()

    if text.lower() in ("none", "no", "n/a", "na", "nil"):
        conv._data["adverse_party_name"] = None
        conv._data["adverse_party_name_tc"] = None
    elif "/" in text:
        parts = [p.strip() for p in text.split("/", 1)]
        conv._data["adverse_party_name"] = parts[0]
        conv._data["adverse_party_name_tc"] = parts[1]
    else:
        conv._data["adverse_party_name"] = text
        conv._data["adverse_party_name_tc"] = None

    summary = _build_summary(conv._data)
    return (
        f"Here's a summary of what you've provided:\n\n{summary}\n\n"
        "Is this correct? (yes/no)",
        State.CONFIRM,
    )


def _handle_confirm(conv: IntakeConversation, message: str) -> tuple[str, State]:
    answer = message.strip().lower()

    if answer in ("yes", "y", "correct", "ok", "confirmed"):
        return (
            "Thank you! Your intake has been submitted. "
            "A solicitor will review your information and contact you soon. "
            "If you need to reach us urgently, please call our office directly.",
            State.COMPLETE,
        )

    if answer in ("no", "n"):
        conv._data.clear()
        return (
            "No problem. Let's start over.\n"
            "May I have your full name, please?",
            State.COLLECT_NAME,
        )

    return ("Please reply 'yes' to confirm or 'no' to start over.", State.CONFIRM)


def _handle_complete(_conv: IntakeConversation, _message: str) -> tuple[str, State]:
    return (
        "Your intake is already complete. If you have a new matter, "
        "please start a new conversation.",
        State.COMPLETE,
    )


def _build_summary(data: dict[str, Any]) -> str:
    lines = []
    if data.get("name_en"):
        name_line = data["name_en"]
        if data.get("name_tc"):
            name_line += f" ({data['name_tc']})"
        lines.append(f"Name: {name_line}")
    if data.get("phone"):
        lines.append(f"Phone: {data['phone']}")
    if data.get("email"):
        lines.append(f"Email: {data['email']}")
    if data.get("matter_type"):
        lines.append(f"Matter: {data['matter_type'].replace('_', ' ').title()}")
    if data.get("matter_description"):
        lines.append(f"Description: {data['matter_description']}")
    if data.get("urgency"):
        lines.append(f"Urgency: {data['urgency'].title()}")
    if data.get("adverse_party_name"):
        ap = data["adverse_party_name"]
        if data.get("adverse_party_name_tc"):
            ap += f" ({data['adverse_party_name_tc']})"
        lines.append(f"Adverse party: {ap}")
    else:
        lines.append("Adverse party: None")
    return "\n".join(lines)


# COLLECT_MATTER has sub-steps; we need a wrapper that dispatches on step_within_state.
def _handle_collect_matter_dispatch(conv: IntakeConversation, message: str) -> tuple[str, State]:
    if conv._step_within_state >= 2:
        return _handle_collect_matter_urgency(conv, message)
    return _handle_collect_matter(conv, message)


_STATE_HANDLERS: dict[State, Any] = {
    State.GREETING: _handle_greeting,
    State.COLLECT_NAME: _handle_collect_name,
    State.COLLECT_CONTACT: _handle_collect_contact,
    State.COLLECT_MATTER: _handle_collect_matter_dispatch,
    State.COLLECT_ADVERSE_PARTY: _handle_collect_adverse_party,
    State.CONFIRM: _handle_confirm,
    State.COMPLETE: _handle_complete,
    State.HUMAN_ESCALATION: _handle_complete,
}
