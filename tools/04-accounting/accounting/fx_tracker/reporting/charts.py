"""FX exposure and rate visualization using matplotlib."""

from __future__ import annotations

import io
import logging
from datetime import date
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.accounting.fx.charts")


def generate_exposure_pie(db_path: str | Path, output_path: str | Path | None = None) -> bytes:
    """Generate a pie chart of currency exposure by net HKD amount.

    Returns PNG bytes. Optionally writes to output_path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from accounting.fx_tracker.calculations.exposure import calculate_exposure

    exposures = calculate_exposure(db_path)

    if not exposures:
        return _empty_chart("No open FX positions")

    labels = [e["currency"] for e in exposures]
    sizes = [abs(e["net_exposure_hkd"]) for e in exposures]
    colors_map = _currency_colors()
    colors = [colors_map.get(label, "#888888") for label in labels]

    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#0d1117")

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct="%1.1f%%",
        startangle=90,
        textprops={"color": "white", "fontsize": 10},
    )

    for autotext in autotexts:
        autotext.set_color("white")
        autotext.set_fontsize(9)

    ax.set_title("Currency Exposure (Net HKD)", color="white", fontsize=14, pad=20)

    legend_labels = [
        f"{e['currency']}: HKD {e['net_exposure_hkd']:,.0f} ({e['direction']})"
        for e in exposures
    ]
    ax.legend(
        wedges, legend_labels,
        loc="lower left",
        fontsize=8,
        facecolor="#161b22",
        edgecolor="#30363d",
        labelcolor="white",
    )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    png_bytes = buf.read()

    if output_path:
        Path(output_path).write_bytes(png_bytes)

    return png_bytes


def generate_rate_history_chart(
    currency: str,
    db_path: str | Path,
    days: int = 30,
    output_path: str | Path | None = None,
) -> bytes:
    """Generate a line chart of exchange rate history for a currency pair.

    Returns PNG bytes. Optionally writes to output_path.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    currency = currency.upper()

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT date, mid_rate, buying_tt, selling_tt
               FROM exchange_rates
               WHERE target_currency = ?
               ORDER BY date DESC
               LIMIT ?""",
            (currency, days),
        ).fetchall()

    if not rows:
        return _empty_chart(f"No rate data for {currency}")

    rows = list(reversed(rows))
    dates = [date.fromisoformat(r["date"]) for r in rows]
    mid_rates = [r["mid_rate"] for r in rows]
    buying = [r["buying_tt"] for r in rows if r["buying_tt"]]
    selling = [r["selling_tt"] for r in rows if r["selling_tt"]]

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    ax.plot(dates, mid_rates, color="#58a6ff", linewidth=2, label="Mid Rate")

    if buying and len(buying) == len(dates):
        ax.fill_between(dates, buying, selling, alpha=0.15, color="#58a6ff", label="Bid/Ask Spread")

    ax.set_title(f"{currency}/HKD Exchange Rate", color="white", fontsize=14)
    ax.set_xlabel("Date", color="#8b949e", fontsize=10)
    ax.set_ylabel("Rate (HKD)", color="#8b949e", fontsize=10)

    ax.tick_params(colors="#8b949e")
    ax.spines["bottom"].set_color("#30363d")
    ax.spines["left"].set_color("#30363d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=1))
    fig.autofmt_xdate()

    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)
    ax.grid(True, alpha=0.1, color="#30363d")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    png_bytes = buf.read()

    if output_path:
        Path(output_path).write_bytes(png_bytes)

    return png_bytes


def generate_gains_losses_bar(
    db_path: str | Path,
    output_path: str | Path | None = None,
) -> bytes:
    """Generate a grouped bar chart of realized G/L by currency."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    with get_db(db_path) as conn:
        rows = conn.execute(
            """SELECT currency,
                      SUM(CASE WHEN realized_gain_loss > 0 THEN realized_gain_loss ELSE 0 END) as gains,
                      SUM(CASE WHEN realized_gain_loss < 0 THEN realized_gain_loss ELSE 0 END) as losses
               FROM fx_transactions
               WHERE is_settled = 1 AND realized_gain_loss IS NOT NULL
               GROUP BY currency
               ORDER BY currency"""
        ).fetchall()

    if not rows:
        return _empty_chart("No realized G/L data")

    currencies = [r["currency"] for r in rows]
    gains = [r["gains"] for r in rows]
    losses = [r["losses"] for r in rows]

    x = np.arange(len(currencies))
    width = 0.35

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")

    ax.bar(x - width / 2, gains, width, label="Gains", color="#3fb950")
    ax.bar(x + width / 2, losses, width, label="Losses", color="#f85149")

    ax.set_title("Realized FX Gains / Losses by Currency", color="white", fontsize=14)
    ax.set_ylabel("HKD", color="#8b949e", fontsize=10)
    ax.set_xticks(x)
    ax.set_xticklabels(currencies, color="#8b949e")
    ax.tick_params(colors="#8b949e")

    ax.spines["bottom"].set_color("#30363d")
    ax.spines["left"].set_color("#30363d")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.axhline(y=0, color="#30363d", linewidth=0.8)
    ax.legend(facecolor="#161b22", edgecolor="#30363d", labelcolor="white", fontsize=9)
    ax.grid(True, axis="y", alpha=0.1, color="#30363d")

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    png_bytes = buf.read()

    if output_path:
        Path(output_path).write_bytes(png_bytes)

    return png_bytes


def _empty_chart(message: str) -> bytes:
    """Generate a placeholder chart with a message when no data is available."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4))
    fig.patch.set_facecolor("#0d1117")
    ax.set_facecolor("#161b22")
    ax.text(
        0.5, 0.5, message,
        ha="center", va="center",
        fontsize=14, color="#8b949e",
        transform=ax.transAxes,
    )
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.read()


def _currency_colors() -> dict[str, str]:
    return {
        "USD": "#58a6ff",
        "EUR": "#3fb950",
        "GBP": "#d2a8ff",
        "JPY": "#f85149",
        "CNH": "#f0883e",
        "AUD": "#56d4dd",
        "CAD": "#db61a2",
        "SGD": "#7ee787",
        "CHF": "#e3b341",
        "NZD": "#79c0ff",
    }
