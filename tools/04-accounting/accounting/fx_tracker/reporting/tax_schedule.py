"""IRD-compliant FX schedule for Profits Tax computation.

Separates FX gains/losses into:
- Revenue nature: Arising from normal trade transactions (taxable / deductible)
- Capital nature: Arising from capital transactions (generally not taxable)

Under Hong Kong Profits Tax (IRO s.14), only profits arising in or derived from
Hong Kong from a trade, profession, or business are chargeable. FX gains on
revenue transactions are assessable; FX gains on capital transactions are not.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.tax_schedule")


def generate_tax_schedule(
    db_path: str | Path,
    assessment_year: str | None = None,
) -> dict[str, Any]:
    """Generate an IRD-compliant FX gains/losses schedule.

    Returns a structured dict suitable for inclusion in the Profits Tax
    computation (supplementary schedule for exchange differences).
    """
    with get_db(db_path) as conn:
        settled = [dict(r) for r in conn.execute(
            """SELECT id, transaction_date, settled_date, description, currency,
                      foreign_amount, exchange_rate, settlement_rate,
                      hkd_amount, settlement_hkd, realized_gain_loss, nature, reference
               FROM fx_transactions
               WHERE is_settled = 1 AND realized_gain_loss IS NOT NULL
               ORDER BY settled_date"""
        ).fetchall()]

        unrealized = [dict(r) for r in conn.execute(
            """SELECT id, period_end_date, currency, outstanding_foreign_amount,
                      original_hkd_amount, closing_rate, revalued_hkd_amount,
                      unrealized_gain_loss
               FROM revaluations
               ORDER BY period_end_date DESC"""
        ).fetchall()]

    revenue_gains: list[dict[str, Any]] = []
    revenue_losses: list[dict[str, Any]] = []
    capital_gains: list[dict[str, Any]] = []
    capital_losses: list[dict[str, Any]] = []

    for tx in settled:
        entry = _format_schedule_entry(tx)
        gl = tx["realized_gain_loss"]

        if tx.get("nature") == "capital":
            (capital_gains if gl >= 0 else capital_losses).append(entry)
        else:
            (revenue_gains if gl >= 0 else revenue_losses).append(entry)

    unrealized_entries = [_format_unrealized_entry(r) for r in unrealized]

    total_revenue_gain = sum(e["gain_loss"] for e in revenue_gains)
    total_revenue_loss = sum(e["gain_loss"] for e in revenue_losses)
    total_capital_gain = sum(e["gain_loss"] for e in capital_gains)
    total_capital_loss = sum(e["gain_loss"] for e in capital_losses)
    total_unrealized = sum(r["unrealized_gain_loss"] for r in unrealized)

    net_revenue = total_revenue_gain + total_revenue_loss
    net_capital = total_capital_gain + total_capital_loss

    schedule = {
        "assessment_year": assessment_year or _current_assessment_year(),
        "generated_at": date.today().isoformat(),
        "realized": {
            "revenue": {
                "gains": revenue_gains,
                "losses": revenue_losses,
                "total_gains": round(total_revenue_gain, 2),
                "total_losses": round(total_revenue_loss, 2),
                "net": round(net_revenue, 2),
                "tax_treatment": "assessable" if net_revenue > 0 else "deductible",
            },
            "capital": {
                "gains": capital_gains,
                "losses": capital_losses,
                "total_gains": round(total_capital_gain, 2),
                "total_losses": round(total_capital_loss, 2),
                "net": round(net_capital, 2),
                "tax_treatment": "not_taxable",
                "note": "Capital FX gains/losses excluded from Profits Tax under IRO s.14",
            },
        },
        "unrealized": {
            "entries": unrealized_entries,
            "total": round(total_unrealized, 2),
            "tax_treatment": "timing_difference",
            "note": "Unrealized FX differences — reverse in following period",
        },
        "summary": {
            "net_revenue_fx": round(net_revenue, 2),
            "net_capital_fx": round(net_capital, 2),
            "net_unrealized_fx": round(total_unrealized, 2),
            "assessable_amount": round(net_revenue, 2),
            "add_back_capital_loss": round(abs(min(net_capital, 0)), 2),
            "exclude_capital_gain": round(max(net_capital, 0), 2),
        },
    }

    return schedule


def _format_schedule_entry(tx: dict[str, Any]) -> dict[str, Any]:
    return {
        "tx_id": tx["id"],
        "date": tx.get("settled_date") or tx["transaction_date"],
        "description": tx.get("description", ""),
        "currency": tx["currency"],
        "foreign_amount": tx["foreign_amount"],
        "original_rate": tx["exchange_rate"],
        "settlement_rate": tx.get("settlement_rate"),
        "gain_loss": tx["realized_gain_loss"],
        "nature": tx.get("nature", "revenue"),
        "reference": tx.get("reference", ""),
    }


def _format_unrealized_entry(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "reval_id": r["id"],
        "period_end": r["period_end_date"],
        "currency": r["currency"],
        "outstanding_amount": r["outstanding_foreign_amount"],
        "closing_rate": r["closing_rate"],
        "unrealized_gain_loss": r["unrealized_gain_loss"],
    }


def _current_assessment_year() -> str:
    """Determine the current IRD assessment year (April–March)."""
    today = date.today()
    if today.month >= 4:
        return f"{today.year}/{str(today.year + 1)[2:]}"
    return f"{today.year - 1}/{str(today.year)[2:]}"
