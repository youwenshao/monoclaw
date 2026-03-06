"""Daily digest — summarises yesterday's business and outstanding tasks."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db


async def generate_daily_digest(
    db_path: str | Path,
    llm: Any = None,
    language: str = "en",
) -> dict[str, Any]:
    """Collect KPIs and return a structured digest dict.

    Keys: ``yesterday_revenue``, ``pending_messages``,
    ``low_stock_items``, ``upcoming_deadlines``.
    """
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    with get_db(db_path) as conn:
        rev_row = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS rev FROM sales WHERE DATE(sale_date) = ?",
            (yesterday,),
        ).fetchone()
        yesterday_revenue: float = rev_row["rev"]

        tx_count = conn.execute(
            "SELECT COUNT(*) FROM sales WHERE DATE(sale_date) = ?", (yesterday,)
        ).fetchone()[0]

        pending = conn.execute(
            "SELECT COUNT(*) FROM whatsapp_messages WHERE requires_followup = 1"
        ).fetchone()[0]

        low_stock = [dict(r) for r in conn.execute(
            "SELECT item_name, item_name_tc, current_stock, low_stock_threshold FROM inventory WHERE current_stock <= low_stock_threshold"
        ).fetchall()]

        today_expenses = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM expenses WHERE expense_date = ?",
            (yesterday,),
        ).fetchone()["total"]

    digest_data: dict[str, Any] = {
        "date": yesterday,
        "yesterday_revenue": round(yesterday_revenue, 2),
        "transaction_count": tx_count,
        "pending_messages": pending,
        "low_stock_items": low_stock,
        "yesterday_expenses": round(today_expenses, 2),
        "upcoming_deadlines": [],
    }

    return digest_data


def format_digest_message(digest_data: dict[str, Any], language: str = "en") -> str:
    """Format digest into a human-friendly WhatsApp/Telegram message."""
    d = digest_data

    if language == "tc":
        lines = [
            f"📊 每日業務摘要 — {d['date']}",
            f"💰 昨日營收: HK${d['yesterday_revenue']:,.2f} ({d['transaction_count']} 筆交易)",
            f"💸 昨日開支: HK${d['yesterday_expenses']:,.2f}",
            f"📱 待處理訊息: {d['pending_messages']}",
        ]
        if d["low_stock_items"]:
            lines.append(f"⚠️ 庫存不足項目: {len(d['low_stock_items'])}")
            for item in d["low_stock_items"][:5]:
                name = item.get("item_name_tc") or item.get("item_name", "?")
                lines.append(f"  • {name}: 剩餘 {item['current_stock']}")
        else:
            lines.append("✅ 庫存充足")
    else:
        lines = [
            f"📊 Daily Business Digest — {d['date']}",
            f"💰 Yesterday's Revenue: HK${d['yesterday_revenue']:,.2f} ({d['transaction_count']} transactions)",
            f"💸 Yesterday's Expenses: HK${d['yesterday_expenses']:,.2f}",
            f"📱 Pending Messages: {d['pending_messages']}",
        ]
        if d["low_stock_items"]:
            lines.append(f"⚠️ Low Stock Items: {len(d['low_stock_items'])}")
            for item in d["low_stock_items"][:5]:
                lines.append(f"  • {item.get('item_name', '?')}: {item['current_stock']} remaining")
        else:
            lines.append("✅ Inventory levels OK")

    return "\n".join(lines)
