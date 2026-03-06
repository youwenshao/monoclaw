"""WhatsApp template messages with SMS fallback. Bilingual Cantonese/English."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger("openclaw.fnb.no-show-shield.messenger")

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def _load_template(name: str) -> dict[str, Any]:
    path = TEMPLATE_DIR / name
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_hk_phone(phone: str) -> bool:
    return bool(HK_PHONE_RE.match(phone))


class Messenger:
    """Sends booking confirmations via WhatsApp (primary) or SMS (fallback).

    Requires Twilio credentials in config for actual delivery.
    When credentials are absent, messages are logged but not sent (dry-run).
    """

    def __init__(
        self,
        twilio_account_sid: str = "",
        twilio_auth_token: str = "",
        twilio_whatsapp_from: str = "",
        twilio_sms_from: str = "",
        default_language: str = "zh",
        restaurant_name: str = "",
    ) -> None:
        self.twilio_account_sid = twilio_account_sid
        self.twilio_auth_token = twilio_auth_token
        self.twilio_whatsapp_from = twilio_whatsapp_from
        self.twilio_sms_from = twilio_sms_from
        self.default_language = default_language
        self.restaurant_name = restaurant_name
        self.default_channel = "whatsapp"

        self._templates: dict[str, dict] = {}
        self._client: Any = None

    @property
    def twilio_configured(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token)

    def _get_twilio_client(self) -> Any:
        if self._client is None and self.twilio_configured:
            try:
                from twilio.rest import Client
                self._client = Client(self.twilio_account_sid, self.twilio_auth_token)
            except ImportError:
                logger.warning("twilio package not installed, running in dry-run mode")
        return self._client

    def _get_template(self, name: str) -> dict:
        if name not in self._templates:
            self._templates[name] = _load_template(name)
        return self._templates[name]

    def _resolve_step_body(
        self,
        step_label: str,
        language: str,
        booking_id: int,
        extra_vars: dict[str, str] | None = None,
    ) -> tuple[str, str]:
        """Resolve template body for a given step and language.

        Returns (subject, body) with placeholders filled.
        """
        template_file = f"confirm_{language}.yaml"
        try:
            tpl = self._get_template(template_file)
        except FileNotFoundError:
            tpl = self._get_template("confirm_en.yaml")

        steps = tpl.get("steps", [])
        match = next((s for s in steps if s["timing"] == step_label), None)
        if not match:
            match = steps[0] if steps else {"subject": "Booking Update", "body": "Booking #{booking_id}"}

        variables = {
            "booking_id": str(booking_id),
            "restaurant_name": self.restaurant_name,
            **(extra_vars or {}),
        }

        subject = match["subject"]
        body = match["body"]
        for key, val in variables.items():
            body = body.replace(f"[{key}]", val)
            body = body.replace(f"{{{key}}}", val)
            subject = subject.replace(f"[{key}]", val)
            subject = subject.replace(f"{{{key}}}", val)

        return subject, body

    def send_confirmation(
        self,
        phone: str,
        booking_id: int,
        step_label: str = "at_booking",
        language: str | None = None,
        extra_vars: dict[str, str] | None = None,
    ) -> bool:
        """Send a confirmation message. Returns True on success."""
        lang = language or self.default_language
        if not validate_hk_phone(phone):
            logger.error("Invalid HK phone number: %s", phone)
            return False

        subject, body = self._resolve_step_body(step_label, lang, booking_id, extra_vars)

        if self._send_whatsapp(phone, body):
            return True

        logger.info("WhatsApp failed for %s, falling back to SMS", phone)
        return self._send_sms(phone, body)

    def send_deposit_request(
        self,
        phone: str,
        booking_id: int,
        amount: str,
        language: str | None = None,
    ) -> bool:
        """Send a deposit request message."""
        lang = language or self.default_language
        if not validate_hk_phone(phone):
            logger.error("Invalid HK phone number: %s", phone)
            return False

        try:
            tpl = self._get_template("deposit_request.yaml")
        except FileNotFoundError:
            logger.error("deposit_request.yaml template not found")
            return False

        messages = tpl.get("messages", {})
        msg_tpl = messages.get(lang, messages.get("en", {}))
        body = msg_tpl.get("body", "")
        body = body.replace("[restaurant_name]", self.restaurant_name)
        body = body.replace("[booking_id]", str(booking_id))
        body = body.replace("[amount]", amount)
        body = body.replace("{restaurant_name}", self.restaurant_name)
        body = body.replace("{booking_id}", str(booking_id))
        body = body.replace("{amount}", amount)

        if self._send_whatsapp(phone, body):
            return True
        return self._send_sms(phone, body)

    def send_waitlist_offer(
        self,
        phone: str,
        date: str,
        time: str,
        party_size: int,
        language: str | None = None,
    ) -> bool:
        """Send a waitlist table offer."""
        lang = language or self.default_language
        if not validate_hk_phone(phone):
            return False

        if lang == "zh":
            body = (
                f"您好！{self.restaurant_name}而家有位喇！"
                f"日期：{date}，時間：{time}，{party_size}位。"
                f"請喺15分鐘內回覆「接受」確認訂位。多謝！🎉"
            )
        else:
            body = (
                f"Great news! A table is now available at {self.restaurant_name}. "
                f"Date: {date}, Time: {time}, Party of {party_size}. "
                f"Reply ACCEPT within 15 minutes to confirm. Thank you! 🎉"
            )

        if self._send_whatsapp(phone, body):
            return True
        return self._send_sms(phone, body)

    def _send_whatsapp(self, phone: str, body: str) -> bool:
        client = self._get_twilio_client()
        if not client or not self.twilio_whatsapp_from:
            logger.info("[DRY-RUN] WhatsApp to %s: %s", phone, body[:80])
            return True

        try:
            client.messages.create(
                from_=f"whatsapp:{self.twilio_whatsapp_from}",
                to=f"whatsapp:{phone}",
                body=body,
            )
            logger.info("WhatsApp sent to %s", phone)
            return True
        except Exception:
            logger.exception("WhatsApp send failed for %s", phone)
            return False

    def _send_sms(self, phone: str, body: str) -> bool:
        client = self._get_twilio_client()
        if not client or not self.twilio_sms_from:
            logger.info("[DRY-RUN] SMS to %s: %s", phone, body[:80])
            return True

        try:
            client.messages.create(
                from_=self.twilio_sms_from,
                to=phone,
                body=body,
            )
            logger.info("SMS sent to %s", phone)
            return True
        except Exception:
            logger.exception("SMS send failed for %s", phone)
            return False
