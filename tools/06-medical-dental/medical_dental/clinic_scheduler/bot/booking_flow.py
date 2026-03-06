"""Multi-step booking conversation state machine for WhatsApp/Telegram."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.scheduler.booking_flow")


class FlowState(str, Enum):
    INIT = "INIT"
    SELECT_DOCTOR = "SELECT_DOCTOR"
    SELECT_SERVICE = "SELECT_SERVICE"
    SELECT_DATE = "SELECT_DATE"
    SELECT_TIME = "SELECT_TIME"
    CONFIRM = "CONFIRM"
    DONE = "DONE"


PROMPTS: dict[FlowState, dict[str, str]] = {
    FlowState.INIT: {
        "en": "Welcome! Would you like to book an appointment? Type 'book' to start.",
        "tc": "歡迎！想預約診症嗎？輸入「預約」開始。",
    },
    FlowState.SELECT_DOCTOR: {
        "en": "Please choose a doctor:\n{options}\nReply with the number.",
        "tc": "請選擇醫生：\n{options}\n輸入數字選擇。",
    },
    FlowState.SELECT_SERVICE: {
        "en": "What type of service?\n1. GP Consultation\n2. Specialist\n3. Dental Cleaning\n4. Dental Procedure\n5. Follow-up\nReply with the number.",
        "tc": "請選擇服務類型：\n1. 普通科門診\n2. 專科診症\n3. 洗牙\n4. 牙科手術\n5. 覆診\n輸入數字選擇。",
    },
    FlowState.SELECT_DATE: {
        "en": "Which date? (format: YYYY-MM-DD)\nOr type 'tomorrow', 'next Monday', etc.",
        "tc": "請選擇日期（格式：YYYY-MM-DD）\n或輸入「明天」、「下周一」等。",
    },
    FlowState.SELECT_TIME: {
        "en": "Available times:\n{options}\nReply with the number.",
        "tc": "可預約時段：\n{options}\n輸入數字選擇。",
    },
    FlowState.CONFIRM: {
        "en": "Please confirm your booking:\n{summary}\nReply 'yes' to confirm or 'no' to cancel.",
        "tc": "請確認預約：\n{summary}\n輸入「確認」或「取消」。",
    },
    FlowState.DONE: {
        "en": "Your appointment #{appt_id} has been booked! We'll send a reminder before your visit.",
        "tc": "預約 #{appt_id} 已確認！我們會在診症前發送提醒。",
    },
}

SERVICE_MAP: dict[str, str] = {
    "1": "gp",
    "2": "specialist",
    "3": "dental_cleaning",
    "4": "dental_procedure",
    "5": "follow_up",
}

SERVICE_LABELS: dict[str, dict[str, str]] = {
    "gp": {"en": "GP Consultation", "tc": "普通科門診"},
    "specialist": {"en": "Specialist", "tc": "專科診症"},
    "dental_cleaning": {"en": "Dental Cleaning", "tc": "洗牙"},
    "dental_procedure": {"en": "Dental Procedure", "tc": "牙科手術"},
    "follow_up": {"en": "Follow-up", "tc": "覆診"},
}


@dataclass
class BookingFlow:
    """State machine driving a multi-turn booking conversation."""

    language: str = "en"
    state: FlowState = FlowState.INIT
    collected: dict[str, Any] = field(default_factory=dict)
    doctors: list[dict[str, Any]] = field(default_factory=list)
    available_slots: list[dict[str, str]] = field(default_factory=list)

    def get_state(self) -> str:
        return self.state.value

    def reset(self) -> None:
        self.state = FlowState.INIT
        self.collected.clear()
        self.doctors.clear()
        self.available_slots.clear()

    def advance(self, user_input: str) -> str:
        user_input = user_input.strip()
        lang = self.language

        if self.state == FlowState.INIT:
            self.state = FlowState.SELECT_DOCTOR
            return self._doctor_prompt(lang)

        if self.state == FlowState.SELECT_DOCTOR:
            return self._handle_doctor_selection(user_input, lang)

        if self.state == FlowState.SELECT_SERVICE:
            return self._handle_service_selection(user_input, lang)

        if self.state == FlowState.SELECT_DATE:
            return self._handle_date_input(user_input, lang)

        if self.state == FlowState.SELECT_TIME:
            return self._handle_time_selection(user_input, lang)

        if self.state == FlowState.CONFIRM:
            return self._handle_confirmation(user_input, lang)

        return PROMPTS[FlowState.INIT][lang]

    def set_doctors(self, doctors: list[dict[str, Any]]) -> None:
        self.doctors = doctors

    def set_available_slots(self, slots: list[dict[str, str]]) -> None:
        self.available_slots = slots

    def set_appointment_id(self, appt_id: int) -> None:
        self.collected["appointment_id"] = appt_id

    # ------------------------------------------------------------------

    def _doctor_prompt(self, lang: str) -> str:
        if not self.doctors:
            fallback = {
                "en": "No doctors available. Please contact the clinic directly.",
                "tc": "目前沒有可預約的醫生，請直接聯絡診所。",
            }
            return fallback[lang]

        name_key = "name_tc" if lang == "tc" else "name_en"
        lines = [f"{i + 1}. {d.get(name_key, d.get('name_en', ''))}" for i, d in enumerate(self.doctors)]
        options = "\n".join(lines)
        return PROMPTS[FlowState.SELECT_DOCTOR][lang].format(options=options)

    def _handle_doctor_selection(self, text: str, lang: str) -> str:
        try:
            idx = int(text) - 1
            if 0 <= idx < len(self.doctors):
                doctor = self.doctors[idx]
                self.collected["doctor_id"] = doctor["id"]
                self.collected["doctor_name"] = doctor.get("name_en", "")
                self.state = FlowState.SELECT_SERVICE
                return PROMPTS[FlowState.SELECT_SERVICE][lang]
        except ValueError:
            pass
        return self._doctor_prompt(lang)

    def _handle_service_selection(self, text: str, lang: str) -> str:
        service = SERVICE_MAP.get(text)
        if service:
            self.collected["service_type"] = service
            self.state = FlowState.SELECT_DATE
            return PROMPTS[FlowState.SELECT_DATE][lang]
        return PROMPTS[FlowState.SELECT_SERVICE][lang]

    def _handle_date_input(self, text: str, lang: str) -> str:
        parsed = self._parse_date(text)
        if parsed:
            self.collected["appointment_date"] = parsed
            self.state = FlowState.SELECT_TIME
            return self._time_prompt(lang)
        error = {
            "en": "Sorry, I couldn't understand that date. Please use YYYY-MM-DD format.",
            "tc": "抱歉，無法辨識日期，請使用 YYYY-MM-DD 格式。",
        }
        return error[lang]

    def _time_prompt(self, lang: str) -> str:
        if not self.available_slots:
            no_slots = {
                "en": "No available time slots for this date. Please choose another date (YYYY-MM-DD).",
                "tc": "該日期沒有可預約時段，請選擇其他日期（YYYY-MM-DD）。",
            }
            self.state = FlowState.SELECT_DATE
            return no_slots[lang]

        lines = [f"{i + 1}. {s['start_time']} - {s['end_time']}" for i, s in enumerate(self.available_slots)]
        options = "\n".join(lines)
        return PROMPTS[FlowState.SELECT_TIME][lang].format(options=options)

    def _handle_time_selection(self, text: str, lang: str) -> str:
        try:
            idx = int(text) - 1
            if 0 <= idx < len(self.available_slots):
                slot = self.available_slots[idx]
                self.collected["start_time"] = slot["start_time"]
                self.collected["end_time"] = slot["end_time"]
                self.collected["room"] = slot.get("room", "")
                self.state = FlowState.CONFIRM
                return self._confirmation_prompt(lang)
        except ValueError:
            pass
        return self._time_prompt(lang)

    def _confirmation_prompt(self, lang: str) -> str:
        svc = self.collected.get("service_type", "gp")
        svc_label = SERVICE_LABELS.get(svc, {}).get(lang, svc)
        doctor = self.collected.get("doctor_name", "")
        appt_date = self.collected.get("appointment_date", "")
        start = self.collected.get("start_time", "")
        end = self.collected.get("end_time", "")

        if lang == "tc":
            summary = (
                f"醫生：{doctor}\n"
                f"服務：{svc_label}\n"
                f"日期：{appt_date}\n"
                f"時間：{start} - {end}"
            )
        else:
            summary = (
                f"Doctor: {doctor}\n"
                f"Service: {svc_label}\n"
                f"Date: {appt_date}\n"
                f"Time: {start} - {end}"
            )
        return PROMPTS[FlowState.CONFIRM][lang].format(summary=summary)

    def _handle_confirmation(self, text: str, lang: str) -> str:
        lower = text.lower()
        if lower in ("yes", "y", "確認", "confirm", "ok"):
            self.state = FlowState.DONE
            appt_id = self.collected.get("appointment_id", "")
            return PROMPTS[FlowState.DONE][lang].format(appt_id=appt_id)

        if lower in ("no", "n", "取消", "cancel"):
            self.reset()
            cancelled = {
                "en": "Booking cancelled. Type 'book' to start again.",
                "tc": "已取消預約。輸入「預約」重新開始。",
            }
            return cancelled[lang]

        retry = {
            "en": "Please reply 'yes' to confirm or 'no' to cancel.",
            "tc": "請輸入「確認」或「取消」。",
        }
        return retry[lang]

    @staticmethod
    def _parse_date(text: str) -> str | None:
        import re
        from datetime import date, timedelta

        text = text.strip().lower()

        iso_match = re.match(r"^\d{4}-\d{2}-\d{2}$", text)
        if iso_match:
            try:
                date.fromisoformat(text)
                return text
            except ValueError:
                return None

        today = date.today()
        if text in ("today", "今天", "今日"):
            return today.isoformat()
        if text in ("tomorrow", "明天", "明日", "聽日"):
            return (today + timedelta(days=1)).isoformat()

        day_names = {
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
            "星期一": 0, "星期二": 1, "星期三": 2, "星期四": 3,
            "星期五": 4, "星期六": 5, "星期日": 6,
            "周一": 0, "周二": 1, "周三": 2, "周四": 3,
            "周五": 4, "周六": 5, "周日": 6,
        }

        for prefix in ("next ", "下", "下周", "下星期"):
            if text.startswith(prefix):
                day_text = text[len(prefix):]
                target_dow = day_names.get(day_text)
                if target_dow is not None:
                    current_dow = today.weekday()
                    days_ahead = (target_dow - current_dow) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    days_ahead += 7
                    return (today + timedelta(days=days_ahead)).isoformat()

        return None
