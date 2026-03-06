"""PDF export for remittance statements and annual summaries.

Uses reportlab for generation.  Falls back to a plain-text file if
reportlab is not installed.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )
    from reportlab.lib.styles import getSampleStyleSheet

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


def _ensure_dir(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def export_remittance_pdf(
    remittance_data: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Generate a PDF remittance statement.

    Args:
        remittance_data: Dict produced by ``generate_remittance``.
        output_path: Destination file path.

    Returns:
        Resolved Path of the created PDF.
    """
    out = _ensure_dir(Path(output_path))

    if not _HAS_REPORTLAB:
        return _fallback_text(remittance_data, out, kind="remittance")

    doc = SimpleDocTemplate(str(out), pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    elements.append(Paragraph("MPF Remittance Statement", styles["Title"]))
    elements.append(Spacer(1, 6 * mm))

    meta = [
        ["Contribution Month", remittance_data.get("contribution_month", "")],
        ["Trustee", remittance_data.get("trustee", "")],
        ["Generated", remittance_data.get("generated_at", "")],
        ["Employees", str(remittance_data.get("employee_count", 0))],
    ]
    meta_table = Table(meta, colWidths=[50 * mm, 100 * mm])
    meta_table.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ])
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 8 * mm))

    header = [
        "Name",
        "Member #",
        "Relevant Income",
        "ER Mandatory",
        "EE Mandatory",
        "Total",
    ]
    rows = [header]
    for item in remittance_data.get("items", []):
        rows.append([
            item.get("name_en", ""),
            item.get("mpf_member_number", ""),
            f"${item.get('relevant_income', 0):,.2f}",
            f"${item.get('employer_mandatory', 0):,.2f}",
            f"${item.get('employee_mandatory', 0):,.2f}",
            f"${item.get('total_contribution', 0):,.2f}",
        ])

    rows.append([
        "TOTAL",
        "",
        "",
        f"${remittance_data.get('total_employer', 0):,.2f}",
        f"${remittance_data.get('total_employee', 0):,.2f}",
        f"${remittance_data.get('total_amount', 0):,.2f}",
    ])

    col_widths = [45 * mm, 30 * mm, 30 * mm, 28 * mm, 28 * mm, 25 * mm]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f36")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#d4a843")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ALIGN", (2, 1), (-1, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#f5f5f5")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ])
    )
    elements.append(tbl)

    doc.build(elements)
    return out


def export_annual_summary_pdf(
    summary_data: list[dict[str, Any]],
    output_path: str | Path,
) -> Path:
    """Generate a PDF annual MPF summary."""
    out = _ensure_dir(Path(output_path))

    if not _HAS_REPORTLAB:
        return _fallback_text({"employees": summary_data}, out, kind="annual")

    doc = SimpleDocTemplate(str(out), pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    elements.append(Paragraph("Annual MPF Contribution Summary", styles["Title"]))
    elements.append(Spacer(1, 8 * mm))

    header = [
        "Name",
        "Months",
        "Total Income",
        "ER Mandatory",
        "EE Mandatory",
        "Total MPF",
    ]
    rows = [header]
    for emp in summary_data:
        rows.append([
            emp.get("name_en", ""),
            str(emp.get("months_contributed", 0)),
            f"${emp.get('total_income', 0):,.2f}",
            f"${emp.get('total_employer_mandatory', 0):,.2f}",
            f"${emp.get('total_employee_mandatory', 0):,.2f}",
            f"${emp.get('total_contributions', 0):,.2f}",
        ])

    col_widths = [45 * mm, 18 * mm, 30 * mm, 28 * mm, 28 * mm, 28 * mm]
    tbl = Table(rows, colWidths=col_widths)
    tbl.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1f36")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#d4a843")),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
            ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ])
    )
    elements.append(tbl)

    doc.build(elements)
    return out


def _fallback_text(
    data: dict[str, Any], out: Path, kind: str = "remittance"
) -> Path:
    """Plain-text fallback when reportlab is unavailable."""
    out = out.with_suffix(".txt")
    lines = [f"MPF {kind.title()} Report", "=" * 40, ""]
    if kind == "remittance":
        lines.append(f"Month: {data.get('contribution_month', '')}")
        lines.append(f"Trustee: {data.get('trustee', '')}")
        lines.append(f"Total: ${data.get('total_amount', 0):,.2f}")
        lines.append("")
        for item in data.get("items", []):
            lines.append(
                f"  {item.get('name_en', '')}: ${item.get('total_contribution', 0):,.2f}"
            )
    else:
        for emp in data.get("employees", []):
            lines.append(
                f"  {emp.get('name_en', '')}: ${emp.get('total_contributions', 0):,.2f}"
            )
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
