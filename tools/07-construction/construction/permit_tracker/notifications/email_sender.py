"""SMTP email alert sender for permit status notifications."""

from __future__ import annotations

import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

logger = logging.getLogger("openclaw.construction.permit_tracker.notifications.email_sender")


def send_email_alert(
    config: dict[str, Any],
    subject: str,
    body: str,
    recipients: list[str],
) -> bool:
    """Send an email alert via SMTP.

    Args:
        config: Dict with SMTP settings — smtp_host, smtp_port, smtp_user,
                smtp_password, smtp_from, smtp_tls (bool).
        subject: Email subject line.
        body: Plain-text email body.
        recipients: List of recipient email addresses.

    Returns:
        True if the email was sent successfully, False otherwise.
    """
    if not recipients:
        logger.warning("No recipients provided — skipping email")
        return False

    smtp_host = config.get("smtp_host", "")
    smtp_port = int(config.get("smtp_port", 587))
    smtp_user = config.get("smtp_user", "")
    smtp_password = config.get("smtp_password", "")
    smtp_from = config.get("smtp_from", smtp_user)
    use_tls = config.get("smtp_tls", True)

    if not smtp_host:
        logger.warning("SMTP not configured — skipping email alert")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = ", ".join(recipients)

    msg.attach(MIMEText(body, "plain", "utf-8"))

    html_body = _plain_to_html(subject, body)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        if use_tls:
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, recipients, msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.sendmail(smtp_from, recipients, msg.as_string())

        logger.info("Email sent to %s: %s", recipients, subject)
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP authentication failed for %s@%s", smtp_user, smtp_host)
        return False
    except smtplib.SMTPException:
        logger.exception("SMTP error sending email to %s", recipients)
        return False
    except OSError:
        logger.exception("Network error connecting to SMTP %s:%d", smtp_host, smtp_port)
        return False


def _plain_to_html(subject: str, body: str) -> str:
    """Convert a plain-text body to a simple HTML email."""
    escaped = (
        body.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>\n")
    )
    return f"""\
<html>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
             color: #1a1a2e; padding: 20px; max-width: 600px;">
  <div style="border-left: 4px solid #e94560; padding-left: 16px; margin-bottom: 20px;">
    <h2 style="margin: 0 0 8px 0; color: #16213e;">{subject}</h2>
  </div>
  <div style="line-height: 1.6; font-size: 14px;">
    {escaped}
  </div>
  <hr style="border: none; border-top: 1px solid #ddd; margin: 24px 0;">
  <p style="font-size: 11px; color: #999;">
    Sent by MonoClaw Construction Dashboard — PermitTracker
  </p>
</body>
</html>"""
