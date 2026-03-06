"""CIC Site Safety Supervision Scheme (SSSS) compliant report generation."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.safety_form.reporting.ssss")


def generate_ssss_pdf(
    db_path: str | Path,
    workspace: Path,
    site_id: int,
    report_date: str,
) -> Path:
    """Generate a CIC SSSS-compliant safety inspection report PDF.

    Returns the path to the generated PDF file.
    """
    data = _gather_report_data(db_path, site_id, report_date)

    output_dir = Path(workspace) / "reports" / "ssss"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"SSSS_{data['site_name']}_{report_date}.pdf"
    safe_filename = "".join(c if c.isalnum() or c in "-_." else "_" for c in filename)
    output_path = output_dir / safe_filename

    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate,
            Table,
            TableStyle,
            Paragraph,
            Spacer,
            Image,
            PageBreak,
        )

        doc = SimpleDocTemplate(
            str(output_path),
            pagesize=A4,
            leftMargin=15 * mm,
            rightMargin=15 * mm,
            topMargin=20 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SSSSTitle", parent=styles["Heading1"], fontSize=16,
            alignment=1, spaceAfter=6 * mm,
        )
        heading_style = ParagraphStyle(
            "SSSSHeading", parent=styles["Heading2"], fontSize=12,
            spaceBefore=4 * mm, spaceAfter=2 * mm,
        )
        normal_style = styles["Normal"]

        elements: list[Any] = []

        # Header
        elements.append(Paragraph("Site Safety Supervision Scheme (SSSS)", title_style))
        elements.append(Paragraph("Daily Safety Inspection Record", heading_style))
        elements.append(Spacer(1, 4 * mm))

        # Site information table
        site_info = [
            ["Site Name:", data["site_name"], "Date:", report_date],
            ["Address:", data["address"], "District:", data["district"]],
            ["Contractor:", data["contractor"], "CIC Reg:", data["cic_registration"]],
            ["Inspector:", data["inspector"], "Weather:", data["weather"]],
            ["Workers on site:", str(data["worker_count"]), "Temperature:", f"{data['temperature']}°C"],
        ]
        site_table = Table(site_info, colWidths=[30 * mm, 55 * mm, 30 * mm, 55 * mm])
        site_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.95, 0.95, 0.95)),
            ("BACKGROUND", (2, 0), (2, -1), colors.Color(0.95, 0.95, 0.95)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(site_table)
        elements.append(Spacer(1, 6 * mm))

        # Checklist results by category
        elements.append(Paragraph("Inspection Checklist", heading_style))

        for category, items in data["checklist_by_category"].items():
            cat_label = category.replace("_", " ").title()
            elements.append(Paragraph(f"<b>{cat_label}</b>", normal_style))

            table_data = [["#", "Item", "Status", "Notes"]]
            for idx, item in enumerate(items, 1):
                status_text = item["status"].upper()
                table_data.append([
                    str(idx),
                    item["item_description"],
                    status_text,
                    item.get("notes", "") or "",
                ])

            checklist_table = Table(
                table_data,
                colWidths=[8 * mm, 85 * mm, 20 * mm, 57 * mm],
            )
            checklist_table.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.2, 0.3, 0.5)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.Color(0.97, 0.97, 0.97)]),
            ]))
            elements.append(checklist_table)
            elements.append(Spacer(1, 3 * mm))

        # Overall score
        elements.append(Spacer(1, 4 * mm))
        score = data.get("overall_score", 0)
        score_color = "green" if score >= 80 else ("orange" if score >= 60 else "red")
        elements.append(Paragraph(
            f"<b>Overall Score: <font color='{score_color}'>{score:.0f}%</font></b>",
            heading_style,
        ))

        # Photo evidence
        photo_items = [i for cat_items in data["checklist_by_category"].values()
                       for i in cat_items if i.get("photo_path")]
        if photo_items:
            elements.append(PageBreak())
            elements.append(Paragraph("Photo Evidence", heading_style))
            for item in photo_items:
                photo_file = Path(workspace) / item["photo_path"]
                if photo_file.exists():
                    try:
                        elements.append(Paragraph(
                            f"<i>{item['category']} — {item['item_description']}</i>",
                            normal_style,
                        ))
                        elements.append(Image(str(photo_file), width=140 * mm, height=100 * mm))
                        elements.append(Spacer(1, 4 * mm))
                    except Exception:
                        logger.warning("Could not embed photo: %s", photo_file)

        # Footer with signature lines
        elements.append(Spacer(1, 10 * mm))
        sig_data = [
            ["Inspector Signature:", "___________________", "Date:", report_date],
            ["Site Agent Signature:", "___________________", "Date:", "___________"],
        ]
        sig_table = Table(sig_data, colWidths=[35 * mm, 50 * mm, 15 * mm, 40 * mm])
        sig_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(sig_table)

        doc.build(elements)
        logger.info("SSSS PDF generated: %s", output_path)

    except ImportError:
        logger.warning("reportlab not installed — generating plain text fallback")
        output_path = output_path.with_suffix(".txt")
        _generate_text_fallback(output_path, data, report_date)

    return output_path


def _gather_report_data(db_path: str | Path, site_id: int, report_date: str) -> dict:
    """Query the database for all data needed in the SSSS report."""
    with get_db(db_path) as conn:
        site = conn.execute("SELECT * FROM sites WHERE id = ?", (site_id,)).fetchone()
        if not site:
            raise ValueError(f"Site #{site_id} not found")
        site = dict(site)

        inspection = conn.execute(
            "SELECT * FROM daily_inspections WHERE site_id = ? AND inspection_date = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (site_id, report_date),
        ).fetchone()

        inspection_data = dict(inspection) if inspection else {}

        items: list[dict] = []
        if inspection:
            rows = conn.execute(
                "SELECT * FROM checklist_items WHERE inspection_id = ? ORDER BY category, id",
                (inspection["id"],),
            ).fetchall()
            items = [dict(r) for r in rows]

    checklist_by_category: dict[str, list[dict]] = {}
    for item in items:
        cat = item.get("category", "other")
        checklist_by_category.setdefault(cat, []).append(item)

    return {
        "site_name": site.get("site_name", ""),
        "address": site.get("address", ""),
        "district": site.get("district", ""),
        "contractor": site.get("contractor", ""),
        "cic_registration": site.get("cic_registration", ""),
        "inspector": inspection_data.get("inspector", ""),
        "weather": inspection_data.get("weather", ""),
        "temperature": inspection_data.get("temperature", "—"),
        "worker_count": inspection_data.get("worker_count", "—"),
        "overall_score": inspection_data.get("overall_score", 0) or 0,
        "checklist_by_category": checklist_by_category,
    }


def _generate_text_fallback(output_path: Path, data: dict, report_date: str) -> None:
    """Generate a plain-text report when reportlab is unavailable."""
    lines = [
        "=" * 60,
        "SITE SAFETY SUPERVISION SCHEME (SSSS)",
        "Daily Safety Inspection Record",
        "=" * 60,
        f"Site:       {data['site_name']}",
        f"Address:    {data['address']}",
        f"Date:       {report_date}",
        f"Inspector:  {data['inspector']}",
        f"Weather:    {data['weather']}",
        f"Workers:    {data['worker_count']}",
        f"Score:      {data['overall_score']:.0f}%",
        "",
    ]

    for category, items in data["checklist_by_category"].items():
        lines.append(f"--- {category.replace('_', ' ').title()} ---")
        for item in items:
            status = item["status"].upper()
            desc = item["item_description"]
            lines.append(f"  [{status:4s}] {desc}")
        lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Text fallback report generated: %s", output_path)
