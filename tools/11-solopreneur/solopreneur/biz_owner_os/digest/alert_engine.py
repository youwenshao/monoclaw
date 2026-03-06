"""Proactive alert engine — low-stock, follow-up, and messaging alerts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


def check_low_stock_alerts(db_path: str | Path) -> list[dict[str, Any]]:
    """Return alert dicts for every item at or below its low-stock threshold."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT * FROM inventory
               WHERE current_stock <= low_stock_threshold
               ORDER BY current_stock ASC"""
        ).fetchall()

    alerts: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        alerts.append({
            "type": "low_stock",
            "severity": "critical" if item["current_stock"] == 0 else "warning",
            "item_id": item["id"],
            "item_name": item["item_name"],
            "item_name_tc": item.get("item_name_tc", ""),
            "current_stock": item["current_stock"],
            "threshold": item["low_stock_threshold"],
            "suggested_reorder": max(item["low_stock_threshold"] * 2 - item["current_stock"], 0),
            "timestamp": datetime.now().isoformat(),
        })
    return alerts


def check_followup_alerts(db_path: str | Path) -> list[dict[str, Any]]:
    """Return alert dicts for WhatsApp messages requiring follow-up."""
    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT m.*, c.name, c.phone
               FROM whatsapp_messages m
               LEFT JOIN customers c ON c.id = m.customer_id
               WHERE m.requires_followup = 1
               ORDER BY m.timestamp ASC"""
        ).fetchall()

    alerts: list[dict[str, Any]] = []
    for row in rows:
        msg = dict(row)
        alerts.append({
            "type": "followup_needed",
            "severity": "info",
            "message_id": msg["id"],
            "customer_name": msg.get("name", "Unknown"),
            "customer_phone": msg.get("phone", ""),
            "message_preview": (msg.get("message_text", "") or "")[:80],
            "received_at": msg.get("timestamp", ""),
            "timestamp": datetime.now().isoformat(),
        })
    return alerts


async def send_alert(
    alert_data: dict[str, Any],
    messaging_config: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Dispatch an alert via the configured messaging channel.

    Currently returns a status dict; actual Twilio / Telegram dispatch
    is wired up when ``messaging_config`` is provided.
    """
    if not messaging_config:
        return {"status": "skipped", "reason": "no messaging config"}

    twilio_client = messaging_config.get("twilio_client")
    owner_phone = messaging_config.get("owner_phone", "")
    twilio_from = messaging_config.get("twilio_from", "")

    if twilio_client and owner_phone and twilio_from:
        severity = alert_data.get("severity", "info").upper()
        alert_type = alert_data.get("type", "alert")
        message = f"[{severity}] {alert_type}: "

        if alert_type == "low_stock":
            message += (
                f"{alert_data.get('item_name', '?')} — "
                f"stock: {alert_data.get('current_stock', 0)}, "
                f"reorder suggestion: {alert_data.get('suggested_reorder', 0)}"
            )
        elif alert_type == "followup_needed":
            message += (
                f"Message from {alert_data.get('customer_name', '?')}: "
                f"{alert_data.get('message_preview', '')}"
            )
        else:
            message += str(alert_data)

        try:
            twilio_client.messages.create(
                body=message,
                from_=f"whatsapp:{twilio_from}",
                to=f"whatsapp:{owner_phone}",
            )
            return {"status": "sent", "channel": "whatsapp"}
        except Exception as exc:
            return {"status": "error", "reason": str(exc)}

    return {"status": "skipped", "reason": "incomplete messaging config"}
