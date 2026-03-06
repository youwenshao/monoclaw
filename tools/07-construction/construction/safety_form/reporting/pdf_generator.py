"""General-purpose PDF generator for safety inspection reports."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger("openclaw.construction.safety_form.reporting.pdf")


def generate_inspection_pdf(
    db_path: str | Path,
    workspace: Path,
    inspection_id: int,
) -> Path:
    """Generate a PDF report for a completed daily inspection.

    Returns the path to the generated PDF file.
    """
    data = _gather_inspection_data(db_path, inspection_id)

    output_dir = Path(workspace) / "reports" / "inspections"
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = f"inspection_{inspection_id}_{data['inspection_date']}.pdf"
    output_path = output_dir / filename

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
            "InspTitle", parent=styles["Heading1"], fontSize=14,
            alignment=1, spaceAfter=4 * mm,
        )
        heading_style = ParagraphStyle(
            "InspHeading", parent=styles["Heading2"], fontSize=11,
            spaceBefore=4 * mm, spaceAfter=2 * mm,
        )
        normal_style = styles["Normal"]

        elements: list[Any] = []

        # Company header
        elements.append(Paragraph("Daily Safety Inspection Report", title_style))
        elements.append(Spacer(1, 2 * mm))

        # Inspection details
        info_rows = [
            ["Inspection #:", str(inspection_id), "Date:", data["inspection_date"]],
            ["Site:", data["site_name"], "Inspector:", data["inspector"]],
            ["Weather:", data["weather"], "Workers:", str(data["worker_count"])],
            ["Status:", data["status"].upper(), "Score:", f"{data['overall_score']:.0f}%"],
        ]
        info_table = Table(info_rows, colWidths=[25 * mm, 60 * mm, 25 * mm, 60 * mm])
        info_table.setStyle(TableStyle([
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.Color(0.93, 0.93, 0.93)),
            ("BACKGROUND", (2, 0), (2, -1), colors.Color(0.93, 0.93, 0.93)),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(info_table)
        elements.append(Spacer(1, 6 * mm))

        # Checklist items grouped by category
        elements.append(Paragraph("Checklist Results", heading_style))

        for category, items in data["items_by_category"].items():
            cat_label = category.replace("_", " ").title()
            elements.append(Paragraph(f"<b>{cat_label}</b>", normal_style))

            pass_count = sum(1 for i in items if i["status"] == "pass")
            applicable = sum(1 for i in items if i["status"] != "na")
            cat_pct = (pass_count / applicable * 100) if applicable else 0

            rows = [["#", "Description", "Status", "Notes"]]
            for idx, item in enumerate(items, 1):
                status = item["status"].upper()
                rows.append([str(idx), item["item_description"], status, item.get("notes", "") or ""])

            t = Table(rows, colWidths=[8 * mm, 80 * mm, 18 * mm, 64 * mm])
            t.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.25, 0.35, 0.55)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.Color(0.8, 0.8, 0.8)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            elements.append(t)
            elements.append(Paragraph(
                f"<i>Category score: {cat_pct:.0f}%</i>", normal_style,
            ))
            elements.append(Spacer(1, 3 * mm))

        # Deficiencies raised
        if data["deficiencies"]:
            elements.append(Paragraph("Deficiencies Raised", heading_style))
            def_rows = [["Category", "Description", "Severity"]]
            for d in data["deficiencies"]:
                def_rows.append([d["category"], d["description"], d["severity"]])
            dt = Table(def_rows, colWidths=[30 * mm, 100 * mm, 25 * mm])
            dt.setStyle(TableStyle([
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("BACKGROUND", (0, 0), (-1, 0), colors.Color(0.6, 0.15, 0.15)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ]))
            elements.append(dt)

        # Photos
        photo_items = [
            item for items in data["items_by_category"].values()
            for item in items if item.get("photo_path")
        ]
        if photo_items:
            elements.append(Spacer(1, 6 * mm))
            elements.append(Paragraph("Photo Evidence", heading_style))
            for item in photo_items:
                photo_file = Path(workspace) / item["photo_path"]
                if photo_file.exists():
                    try:
                        elements.append(Paragraph(
                            f"<i>{item['category']}: {item['item_description']}</i>",
                            normal_style,
                        ))
                        elements.append(Image(str(photo_file), width=130 * mm, height=90 * mm))
                        elements.append(Spacer(1, 3 * mm))
                    except Exception:
                        logger.warning("Could not embed photo: %s", photo_file)

        # Footer
        elements.append(Spacer(1, 10 * mm))
        elements.append(Paragraph(
            f"<i>Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
            normal_style,
        ))

        doc.build(elements)
        logger.info("Inspection PDF generated: %s", output_path)

    except ImportError:
        logger.warning("reportlab not installed — generating plain text fallback")
        output_path = output_path.with_suffix(".txt")
        _generate_text_fallback(output_path, data)

    return output_path


def _gather_inspection_data(db_path: str | Path, inspection_id: int) -> dict:
    """Query all data for an inspection report."""
    with get_db(db_path) as conn:
        inspection = conn.execute(
            "SELECT di.*, s.site_name FROM daily_inspections di "
            "LEFT JOIN sites s ON di.site_id = s.id WHERE di.id = ?",
            (inspection_id,),
        ).fetchone()
        if not inspection:
            raise ValueError(f"Inspection #{inspection_id} not found")
        inspection = dict(inspection)

        items = [dict(r) for r in conn.execute(
            "SELECT * FROM checklist_items WHERE inspection_id = ? ORDER BY category, id",
            (inspection_id,),
        ).fetchall()]

        deficiencies = [dict(r) for r in conn.execute(
            "SELECT * FROM deficiencies WHERE site_id = ? AND reported_date = ?",
            (inspection["site_id"], inspection["inspection_date"]),
        ).fetchall()]

    items_by_category: dict[str, list[dict]] = {}
    for item in items:
        cat = item.get("category", "other")
        items_by_category.setdefault(cat, []).append(item)

    return {
        "inspection_id": inspection_id,
        "site_name": inspection.get("site_name", ""),
        "inspection_date": inspection.get("inspection_date", ""),
        "inspector": inspection.get("inspector", ""),
        "weather": inspection.get("weather", ""),
        "worker_count": inspection.get("worker_count", 0) or 0,
        "overall_score": inspection.get("overall_score", 0) or 0,
        "status": inspection.get("status", ""),
        "items_by_category": items_by_category,
        "deficiencies": deficiencies,
    }


def _generate_text_fallback(output_path: Path, data: dict) -> None:
    """Generate a text report when reportlab is unavailable."""
    lines = [
        "=" * 60,
        "DAILY SAFETY INSPECTION REPORT",
        "=" * 60,
        f"Inspection #: {data['inspection_id']}",
        f"Site:         {data['site_name']}",
        f"Date:         {data['inspection_date']}",
        f"Inspector:    {data['inspector']}",
        f"Weather:      {data['weather']}",
        f"Workers:      {data['worker_count']}",
        f"Score:        {data['overall_score']:.0f}%",
        f"Status:       {data['status']}",
        "",
    ]

    for category, items in data["items_by_category"].items():
        lines.append(f"--- {category.replace('_', ' ').title()} ---")
        for item in items:
            lines.append(f"  [{item['status'].upper():4s}] {item['item_description']}")
        lines.append("")

    if data["deficiencies"]:
        lines.append("--- Deficiencies ---")
        for d in data["deficiencies"]:
            lines.append(f"  [{d['severity']}] {d['category']}: {d['description']}")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Text fallback report generated: %s", output_path)
