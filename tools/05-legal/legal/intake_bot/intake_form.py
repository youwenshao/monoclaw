"""Generate pre-filled client intake form PDFs using reportlab."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.legal.intake_bot.intake_form")


def generate_intake_form(
    client_data: dict[str, Any],
    matter_data: dict[str, Any],
    output_path: str | Path,
) -> Path:
    """Generate a pre-filled intake form PDF.

    Includes: firm header, client name (EN/TC), contact details, matter type,
    adverse party, urgency, date, and signature line.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import (
        SimpleDocTemplate,
        Paragraph,
        Spacer,
        Table,
        TableStyle,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)

    _register_cjk_font()

    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "IntakeTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=6 * mm,
        alignment=1,
    )
    style_subtitle = ParagraphStyle(
        "IntakeSubtitle",
        parent=styles["Heading2"],
        fontSize=12,
        spaceAfter=4 * mm,
        alignment=1,
        textColor=colors.HexColor("#555555"),
    )
    style_section = ParagraphStyle(
        "SectionHeader",
        parent=styles["Heading3"],
        fontSize=12,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        textColor=colors.HexColor("#1a3a5c"),
    )
    style_body = styles["Normal"]

    elements: list[Any] = []

    elements.append(Paragraph("CLIENT INTAKE FORM", style_title))
    elements.append(Paragraph(
        f"Date: {datetime.now().strftime('%d %B %Y')}",
        style_subtitle,
    ))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("Client Information", style_section))

    name_en = client_data.get("name_en", "")
    name_tc = client_data.get("name_tc", "")
    display_name = name_en
    if name_tc:
        display_name = f"{name_en}  ({name_tc})"

    client_rows = [
        ["Full Name:", display_name],
        ["HKID (last 4):", client_data.get("hkid_last4", "N/A")],
        ["Phone:", client_data.get("phone", "N/A")],
        ["Email:", client_data.get("email", "N/A")],
        ["Source Channel:", client_data.get("source_channel", "N/A")],
    ]

    client_table = Table(client_rows, colWidths=[45 * mm, 115 * mm])
    client_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("LINEBELOW", (1, 0), (1, -1), 0.5, colors.HexColor("#cccccc")),
    ]))
    elements.append(client_table)

    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph("Matter Details", style_section))

    matter_type = matter_data.get("matter_type", "N/A")
    if matter_type and matter_type != "N/A":
        matter_type = matter_type.replace("_", " ").title()

    adverse_en = matter_data.get("adverse_party_name", "")
    adverse_tc = matter_data.get("adverse_party_name_tc", "")
    adverse_display = adverse_en or "N/A"
    if adverse_tc:
        adverse_display = f"{adverse_en}  ({adverse_tc})"

    urgency = matter_data.get("urgency", "normal")
    if urgency:
        urgency = urgency.title()

    matter_rows = [
        ["Matter Type:", matter_type],
        ["Description:", matter_data.get("description", "N/A")],
        ["Adverse Party:", adverse_display],
        ["Urgency:", urgency],
        ["Assigned Solicitor:", matter_data.get("assigned_solicitor", "To be assigned")],
    ]

    matter_table = Table(matter_rows, colWidths=[45 * mm, 115 * mm])
    matter_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ("LINEBELOW", (1, 0), (1, -1), 0.5, colors.HexColor("#cccccc")),
    ]))
    elements.append(matter_table)

    elements.append(Spacer(1, 15 * mm))
    elements.append(Paragraph("Declaration", style_section))
    elements.append(Paragraph(
        "I confirm that the information provided above is true and accurate to the "
        "best of my knowledge. I understand that this form does not constitute a "
        "solicitor-client retainer and that an engagement letter will be provided "
        "separately if the firm agrees to take on the matter.",
        style_body,
    ))

    elements.append(Spacer(1, 15 * mm))

    sig_rows = [
        ["Client Signature:", "_" * 40],
        ["", ""],
        ["Date:", "_" * 40],
    ]
    sig_table = Table(sig_rows, colWidths=[45 * mm, 115 * mm])
    sig_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6 * mm),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    logger.info("Intake form generated: %s", out)
    return out


def _register_cjk_font() -> None:
    """Attempt to register a CJK-capable font for Chinese characters."""
    from reportlab.pdfbase import pdfmetrics

    try:
        pdfmetrics.getFont("Helvetica")
    except KeyError:
        pass

    cjk_font_paths = [
        "/System/Library/Fonts/STHeiti Light.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]

    for font_path in cjk_font_paths:
        if Path(font_path).exists():
            try:
                from reportlab.pdfbase.ttfonts import TTFont
                pdfmetrics.registerFont(TTFont("CJK", font_path, subfontIndex=0))
                logger.debug("Registered CJK font from %s", font_path)
                return
            except Exception:
                continue
