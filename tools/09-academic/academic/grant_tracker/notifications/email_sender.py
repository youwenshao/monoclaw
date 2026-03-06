"""Email notification delivery via SMTP."""

from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger("openclaw.academic.grant_tracker.notifications.email")


def send_email(
    to: str,
    subject: str,
    body: str,
    smtp_host: str = "localhost",
    smtp_port: int = 587,
    smtp_user: str = "",
    smtp_password: str = "",
    from_addr: str = "",
) -> bool:
    """Send an email notification.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body.
        smtp_host: SMTP server hostname.
        smtp_port: SMTP server port (587 for STARTTLS).
        smtp_user: SMTP authentication username (empty to skip auth).
        smtp_password: SMTP authentication password.
        from_addr: Sender address (defaults to smtp_user or a fallback).

    Returns:
        True if the email was sent successfully, False on error.
    """
    sender = from_addr or smtp_user or "grant-tracker@openclaw.local"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg.set_content(body)

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
            server.ehlo()
            if smtp_port == 587:
                try:
                    server.starttls()
                    server.ehlo()
                except smtplib.SMTPNotSupportedError:
                    logger.debug("STARTTLS not supported by %s:%d", smtp_host, smtp_port)
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)

        logger.info("Email sent to %s: %s", to, subject)
        return True
    except Exception:
        logger.exception("Failed to send email to %s", to)
        return False


def format_deadline_email(
    deadline: dict,
    days_remaining: int,
) -> tuple[str, str]:
    """Format a deadline reminder as an email subject and body.

    Returns:
        A (subject, body) tuple.
    """
    scheme = deadline.get("scheme_code", "Unknown")
    name = deadline.get("scheme_name", "")
    agency = deadline.get("agency", "")
    ext_dl = deadline.get("external_deadline", "N/A")
    inst_dl = deadline.get("institutional_deadline")
    url = deadline.get("call_url", "")

    if days_remaining <= 3:
        subject = f"[URGENT] {scheme} grant deadline in {days_remaining} day{'s' if days_remaining != 1 else ''}"
    else:
        subject = f"[Reminder] {scheme} grant deadline in {days_remaining} days"

    body_lines = [
        f"Grant Deadline Reminder",
        f"{'=' * 40}",
        f"",
        f"Scheme: {scheme} – {name}",
        f"Agency: {agency}",
        f"External deadline: {ext_dl}",
        f"Days remaining: {days_remaining}",
    ]

    if inst_dl:
        body_lines.append(f"Institutional deadline: {inst_dl}")

    body_lines.append("")

    if url:
        body_lines.append(f"Call for proposals: {url}")
        body_lines.append("")

    notes = deadline.get("notes")
    if notes:
        body_lines.append(f"Notes: {notes}")
        body_lines.append("")

    if days_remaining <= 7:
        body_lines.extend([
            "Action items:",
            "- Ensure all documents are finalised",
            "- Check institutional submission requirements",
            "- Confirm budget approval from department",
            "",
        ])

    body_lines.append("-- ")
    body_lines.append("GrantTracker (Academic Dashboard)")

    return subject, "\n".join(body_lines)
