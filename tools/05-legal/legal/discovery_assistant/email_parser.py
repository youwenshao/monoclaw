"""Email parsing for .eml and .mbox files."""

from __future__ import annotations

import email
import email.policy
import io
import mailbox
from email.message import EmailMessage
from pathlib import Path
from typing import Any


def _decode_header(value: str | None) -> str:
    if not value:
        return ""
    decoded_parts: list[str] = []
    for part, charset in email.header.decode_header(value):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return " ".join(decoded_parts)


def _extract_body(msg: EmailMessage | email.message.Message) -> str:
    """Extract preferred plain-text body, falling back to stripped HTML."""
    if isinstance(msg, EmailMessage):
        body = msg.get_body(preferencelist=("plain", "html"))
        if body is not None:
            payload = body.get_content()
            if isinstance(payload, str):
                return payload
            if isinstance(payload, bytes):
                return payload.decode("utf-8", errors="replace")
        return ""

    if msg.is_multipart():
        plain_parts: list[str] = []
        html_parts: list[str] = []
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    plain_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
        if plain_parts:
            return "\n".join(plain_parts)
        if html_parts:
            return "\n".join(html_parts)
        return ""

    payload = msg.get_payload(decode=True)
    if payload and isinstance(payload, bytes):
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace")
    return str(payload) if payload else ""


def _collect_attachments(msg: email.message.Message) -> list[dict[str, Any]]:
    """Return metadata dicts for each attachment in the message."""
    attachments: list[dict[str, Any]] = []
    for part in msg.walk():
        disp = part.get("Content-Disposition", "")
        if "attachment" not in disp and part.get_content_maintype() == "multipart":
            continue
        if "attachment" in disp or part.get_filename():
            filename = _decode_header(part.get_filename()) or "unnamed"
            payload = part.get_payload(decode=True)
            attachments.append({
                "filename": filename,
                "content_type": part.get_content_type(),
                "size": len(payload) if payload else 0,
                "data": payload,
            })
    return attachments


def parse_eml(file_path: str | Path) -> dict[str, Any]:
    """Parse a single .eml file and return structured data."""
    path = Path(file_path)
    raw = path.read_bytes()
    msg = email.message_from_bytes(raw, policy=email.policy.default)

    attachments = _collect_attachments(msg)

    return {
        "date": _decode_header(msg.get("Date")),
        "from": _decode_header(msg.get("From")),
        "to": _decode_header(msg.get("To")),
        "cc": _decode_header(msg.get("Cc")),
        "subject": _decode_header(msg.get("Subject")),
        "body": _extract_body(msg),
        "attachments": [
            {"filename": a["filename"], "content_type": a["content_type"], "size": a["size"]}
            for a in attachments
        ],
        "attachment_data": attachments,
        "source_file": path.name,
    }


def parse_mbox(file_path: str | Path) -> list[dict[str, Any]]:
    """Parse an .mbox archive and return a list of parsed messages."""
    path = Path(file_path)
    mbox = mailbox.mbox(str(path))
    results: list[dict[str, Any]] = []

    try:
        for msg in mbox:
            attachments = _collect_attachments(msg)
            results.append({
                "date": _decode_header(msg.get("Date")),
                "from": _decode_header(msg.get("From")),
                "to": _decode_header(msg.get("To")),
                "cc": _decode_header(msg.get("Cc")),
                "subject": _decode_header(msg.get("Subject")),
                "body": _extract_body(msg),
                "attachments": [
                    {"filename": a["filename"], "content_type": a["content_type"], "size": a["size"]}
                    for a in attachments
                ],
                "attachment_data": attachments,
                "source_file": path.name,
            })
    finally:
        mbox.close()

    return results


def extract_attachment_text(attachment_bytes: bytes, content_type: str) -> str:
    """Extract text content from PDF or DOCX attachment bytes."""
    if content_type == "application/pdf" or content_type.endswith("/pdf"):
        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(io.BytesIO(attachment_bytes))
            pages: list[str] = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except Exception:
            return ""

    if (
        content_type
        in (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        )
        or content_type.endswith(".document")
    ):
        try:
            from docx import Document
            doc = Document(io.BytesIO(attachment_bytes))
            return "\n".join(para.text for para in doc.paragraphs if para.text)
        except Exception:
            return ""

    if content_type.startswith("text/"):
        return attachment_bytes.decode("utf-8", errors="replace")

    return ""
