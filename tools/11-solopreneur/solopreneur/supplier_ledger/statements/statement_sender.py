"""Send generated statements via WhatsApp or email."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def send_statement_whatsapp(
    statement_data: dict[str, Any],
    twilio_client: Any,
    from_number: str,
    to_number: str,
) -> bool:
    """Send a statement summary via Twilio WhatsApp.

    Returns ``True`` on success, ``False`` on failure (logged, not raised).
    """
    contact = statement_data.get("contact", {})
    name = contact.get("company_name", "Customer")
    period = f"{statement_data.get('period_start', '')} – {statement_data.get('period_end', '')}"
    opening = statement_data.get("opening_balance", 0)
    closing = statement_data.get("closing_balance", 0)

    body = (
        f"Monthly Statement for {name}\n"
        f"Period: {period}\n"
        f"Opening Balance: HK${opening:,.2f}\n"
        f"Closing Balance: HK${closing:,.2f}\n\n"
        "Please contact us if you have any queries."
    )

    try:
        twilio_client.messages.create(
            body=body,
            from_=f"whatsapp:{from_number}",
            to=f"whatsapp:{to_number}",
        )
        logger.info("WhatsApp statement sent to %s", to_number)
        return True
    except Exception:
        logger.exception("Failed to send WhatsApp statement to %s", to_number)
        return False


def send_statement_email(
    statement_data: dict[str, Any],
    smtp_config: dict[str, Any],
    to_email: str,
) -> bool:
    """Send a statement summary via SMTP email.

    *smtp_config* keys: ``host``, ``port``, ``username``, ``password``,
    ``from_email``, ``use_tls`` (bool, default True).
    """
    contact = statement_data.get("contact", {})
    name = contact.get("company_name", "Customer")
    period = f"{statement_data.get('period_start', '')} – {statement_data.get('period_end', '')}"
    opening = statement_data.get("opening_balance", 0)
    closing = statement_data.get("closing_balance", 0)

    msg = EmailMessage()
    msg["Subject"] = f"Monthly Statement — {period}"
    msg["From"] = smtp_config.get("from_email", smtp_config.get("username", ""))
    msg["To"] = to_email

    body_lines = [
        f"Dear {name},",
        "",
        f"Please find below your account statement for {period}.",
        "",
        f"Opening Balance: HK${opening:,.2f}",
    ]

    for txn in statement_data.get("transactions", []):
        body_lines.append(
            f"  {txn['date']}  {txn['reference']:<20}  HK${txn['amount']:>12,.2f}"
        )

    body_lines += [
        "",
        f"Closing Balance: HK${closing:,.2f}",
        "",
        "Please contact us if you have any queries.",
    ]
    msg.set_content("\n".join(body_lines))

    pdf_path = statement_data.get("pdf_path")
    if pdf_path and Path(pdf_path).exists():
        with open(pdf_path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=Path(pdf_path).name,
            )

    try:
        use_tls = smtp_config.get("use_tls", True)
        smtp_cls = smtplib.SMTP_SSL if use_tls else smtplib.SMTP
        with smtp_cls(smtp_config["host"], int(smtp_config.get("port", 465))) as server:
            if smtp_config.get("username"):
                server.login(smtp_config["username"], smtp_config["password"])
            server.send_message(msg)
        logger.info("Email statement sent to %s", to_email)
        return True
    except Exception:
        logger.exception("Failed to send email statement to %s", to_email)
        return False
