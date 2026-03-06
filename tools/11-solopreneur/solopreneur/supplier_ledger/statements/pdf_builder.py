"""Build statement PDFs using ReportLab (DD/MM/YYYY date format)."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


def _fmt_date(iso: str | None) -> str:
    """Convert YYYY-MM-DD to DD/MM/YYYY."""
    if not iso:
        return ""
    try:
        d = date.fromisoformat(iso)
        return d.strftime("%d/%m/%Y")
    except ValueError:
        return iso


def build_statement_pdf(
    statement_data: dict[str, Any], output_path: str | Path
) -> Path:
    """Render a monthly statement to PDF and return the output path.

    The statement shows opening balance, each transaction, and closing balance
    in DD/MM/YYYY format with HKD currency.
    """
    if not _HAS_REPORTLAB:
        raise RuntimeError(
            "reportlab is required for PDF generation — install it with "
            "'pip install reportlab'"
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    contact = statement_data.get("contact", {})
    company = contact.get("company_name", "N/A")
    period_start = _fmt_date(statement_data.get("period_start"))
    period_end = _fmt_date(statement_data.get("period_end"))
    opening = statement_data.get("opening_balance", 0)
    closing = statement_data.get("closing_balance", 0)
    transactions = statement_data.get("transactions", [])

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "StatementTitle", parent=styles["Title"], fontSize=16, spaceAfter=6
    )
    normal = styles["Normal"]

    elements: list[Any] = []

    elements.append(Paragraph("Account Statement", title_style))
    elements.append(Spacer(1, 4 * mm))

    meta_data = [
        ["To:", company],
        ["Period:", f"{period_start} — {period_end}"],
        ["Date Issued:", datetime.now().strftime("%d/%m/%Y")],
    ]
    meta_table = Table(meta_data, colWidths=[80, 300])
    meta_table.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 8 * mm))

    header = ["Date", "Reference", "Description", "Amount (HKD)", "Balance (HKD)"]
    table_data = [header]

    table_data.append([
        "", "", "Opening Balance", "", f"{opening:,.2f}",
    ])

    for txn in transactions:
        table_data.append([
            _fmt_date(txn.get("date")),
            txn.get("reference", ""),
            txn.get("description", ""),
            f"{txn['amount']:,.2f}",
            f"{txn.get('running_balance', 0):,.2f}",
        ])

    table_data.append([
        "", "", "Closing Balance", "", f"{closing:,.2f}",
    ])

    col_widths = [70, 100, 150, 80, 80]
    txn_table = Table(table_data, colWidths=col_widths, repeatRows=1)
    txn_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f36")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("FONTSIZE", (0, 0), (-1, 0), 9),
            ("ALIGN", (3, 0), (4, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#e8e8e8")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ])
    )
    elements.append(txn_table)
    elements.append(Spacer(1, 10 * mm))
    elements.append(
        Paragraph(
            "Please contact us if you have any queries regarding this statement.",
            normal,
        )
    )

    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )
    doc.build(elements)
    return output
