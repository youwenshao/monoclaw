"""PDF generation for work orders using reportlab."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.defects_manager.work_orders.pdf_export")

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
    )

    _HAS_REPORTLAB = True
except ImportError:
    _HAS_REPORTLAB = False


def generate_work_order_pdf(
    db_path: str | Path,
    workspace: Path,
    work_order_id: int,
) -> Path:
    """Generate a PDF for a work order and return the output path.

    Falls back to a plain-text file if reportlab is unavailable.
    """
    with get_db(db_path) as conn:
        wo = conn.execute(
            "SELECT wo.*, d.category, d.description AS defect_desc, d.floor, d.unit, "
            "d.location_detail, d.priority, d.photo_path, p.property_name "
            "FROM work_orders wo "
            "LEFT JOIN defects d ON wo.defect_id = d.id "
            "LEFT JOIN properties p ON d.property_id = p.id "
            "WHERE wo.id = ?",
            (work_order_id,),
        ).fetchone()
        if not wo:
            raise ValueError(f"Work order #{work_order_id} not found")
        data = dict(wo)

        contractor: dict[str, Any] = {}
        if data.get("contractor_id"):
            c_row = conn.execute(
                "SELECT * FROM contractors WHERE id = ?", (data["contractor_id"],)
            ).fetchone()
            if c_row:
                contractor = dict(c_row)

    out_dir = workspace / "exports" / "work_orders"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"WO-{work_order_id:05d}.pdf"

    if not _HAS_REPORTLAB:
        return _fallback_text(data, contractor, out_path)

    return _build_pdf(data, contractor, out_path)


def _build_pdf(data: dict, contractor: dict, out_path: Path) -> Path:
    doc = SimpleDocTemplate(str(out_path), pagesize=A4)
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    elements.append(Paragraph("WORK ORDER", styles["Title"]))
    elements.append(Spacer(1, 4 * mm))

    header_data = [
        ["Work Order #", str(data.get("id", ""))],
        ["Issue Date", data.get("issue_date", "")],
        ["Property", data.get("property_name", "N/A")],
        ["Priority", (data.get("priority") or "normal").upper()],
        ["Target Completion", data.get("target_completion", "TBD")],
    ]
    header_table = Table(header_data, colWidths=[45 * mm, 120 * mm])
    header_table.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ])
    )
    elements.append(header_table)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Defect Details", styles["Heading2"]))
    defect_data = [
        ["Category", (data.get("category") or "other").replace("_", " ").title()],
        ["Location", f"{data.get('floor', '?')}F / Unit {data.get('unit', '?')}"],
        ["Description", data.get("defect_desc", "")],
    ]
    dt = Table(defect_data, colWidths=[35 * mm, 130 * mm])
    dt.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
        ])
    )
    elements.append(dt)
    elements.append(Spacer(1, 6 * mm))

    elements.append(Paragraph("Scope of Work", styles["Heading2"]))
    elements.append(Paragraph(data.get("scope_of_work", "As per defect report."), styles["Normal"]))
    elements.append(Spacer(1, 6 * mm))

    if contractor:
        elements.append(Paragraph("Contractor", styles["Heading2"]))
        c_data = [
            ["Company", contractor.get("company_name", "")],
            ["Contact", contractor.get("contact_person", "")],
            ["Phone", contractor.get("phone", "")],
            ["Email", contractor.get("email", "")],
        ]
        ct = Table(c_data, colWidths=[35 * mm, 130 * mm])
        ct.setStyle(
            TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TEXTCOLOR", (0, 0), (0, -1), colors.grey),
            ])
        )
        elements.append(ct)
        elements.append(Spacer(1, 6 * mm))

    if data.get("estimated_cost"):
        elements.append(Paragraph(f"Estimated Cost: HK${data['estimated_cost']:,.2f}", styles["Normal"]))
        elements.append(Spacer(1, 4 * mm))

    elements.append(Spacer(1, 20 * mm))
    sig_data = [
        ["Issued By: ___________________", "Accepted By: ___________________"],
        ["Date: ___________________", "Date: ___________________"],
    ]
    sig_table = Table(sig_data, colWidths=[85 * mm, 85 * mm])
    sig_table.setStyle(
        TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ])
    )
    elements.append(sig_table)

    doc.build(elements)
    logger.info("PDF generated: %s", out_path)
    return out_path


def _fallback_text(data: dict, contractor: dict, out_path: Path) -> Path:
    """Plain-text fallback when reportlab is not installed."""
    out_path = out_path.with_suffix(".txt")
    lines = [
        f"WORK ORDER #{data.get('id', '')}",
        "=" * 50,
        f"Issue Date: {data.get('issue_date', '')}",
        f"Property: {data.get('property_name', 'N/A')}",
        f"Priority: {(data.get('priority') or 'normal').upper()}",
        "",
        "DEFECT DETAILS",
        f"  Category: {(data.get('category') or 'other').replace('_', ' ').title()}",
        f"  Location: {data.get('floor', '?')}F / Unit {data.get('unit', '?')}",
        f"  Description: {data.get('defect_desc', '')}",
        "",
        "SCOPE OF WORK",
        f"  {data.get('scope_of_work', 'As per defect report.')}",
    ]
    if contractor:
        lines += [
            "",
            "CONTRACTOR",
            f"  Company: {contractor.get('company_name', '')}",
            f"  Contact: {contractor.get('contact_person', '')}",
            f"  Phone: {contractor.get('phone', '')}",
        ]
    if data.get("estimated_cost"):
        lines.append(f"\nEstimated Cost: HK${data['estimated_cost']:,.2f}")

    out_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Text fallback generated: %s", out_path)
    return out_path
