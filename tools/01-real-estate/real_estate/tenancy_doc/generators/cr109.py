"""Generate a Form CR109 (Notice of New Tenancy) PDF.

Form CR109 must be filed with the Commissioner of Rating and Valuation
within one month of executing a new tenancy. This generator creates
a filled-in PDF that mirrors the fixed-layout government form.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    KeepTogether,
)


PAGE_W, PAGE_H = A4


def _field_row(label: str, value: str, label_width: float = 55 * mm) -> Table:
    """Single label-value row for the form layout."""
    value_width = PAGE_W - label_width - 30 * mm  # page margins
    data = [[label, value]]
    t = Table(data, colWidths=[label_width, value_width])
    t.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (1, 0), (1, 0), 0.5, colors.black),
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
    ]))
    return t


def generate_cr109(tenancy_data: dict, output_dir: Path) -> Path:
    """Create a filled Form CR109 PDF and return the file path.

    ``tenancy_data`` should include::

        property_address, landlord_name, tenant_name,
        monthly_rent, start_date, end_date, term_months

    Optional: ``property_address_zh``, ``landlord_hkid``, ``tenant_hkid``,
    ``landlord_phone``, ``tenant_phone``, ``stamp_duty_amount``.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"cr109_{tenancy_data.get('id', 'draft')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    path = output_dir / filename

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "FormTitle",
        parent=styles["Title"],
        fontSize=14,
        spaceAfter=2 * mm,
    ))
    styles.add(ParagraphStyle(
        "FormSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        alignment=1,
        spaceAfter=4 * mm,
        textColor=colors.HexColor("#333333"),
    ))
    styles.add(ParagraphStyle(
        "Section",
        parent=styles["Heading2"],
        fontSize=10,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
        textColor=colors.HexColor("#2c3e50"),
    ))

    address = tenancy_data.get("property_address", "")
    address_zh = tenancy_data.get("property_address_zh", "")
    landlord = tenancy_data.get("landlord_name", "")
    landlord_hkid = tenancy_data.get("landlord_hkid", "")
    landlord_phone = tenancy_data.get("landlord_phone", "")
    tenant = tenancy_data.get("tenant_name", "")
    tenant_hkid = tenancy_data.get("tenant_hkid", "")
    tenant_phone = tenancy_data.get("tenant_phone", "")
    rent = tenancy_data.get("monthly_rent", 0)
    start = tenancy_data.get("start_date", "")
    end = tenancy_data.get("end_date", "")
    term = tenancy_data.get("term_months", 0)
    stamp_duty = tenancy_data.get("stamp_duty_amount", "")

    elements: list = []

    # ── Header ─────────────────────────────────────────────────────────
    elements.append(Paragraph("FORM CR109", styles["FormTitle"]))
    elements.append(Paragraph(
        "NOTICE OF NEW LETTING OF DOMESTIC PREMISES<br/>"
        "住宅物業新租出的通知書<br/>"
        "(Rating Ordinance, Section 45(2))<br/>"
        "(差餉條例第45(2)條)",
        styles["FormSubtitle"],
    ))

    elements.append(Paragraph(
        "To: The Commissioner of Rating and Valuation, 15/F, Cheung Sha Wan "
        "Government Offices, 303 Cheung Sha Wan Road, Kowloon.",
        styles["Normal"],
    ))
    elements.append(Paragraph(
        "致：差餉物業估價署署長，九龍長沙灣道303號長沙灣政府合署15樓",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 5 * mm))

    # ── Part I: Particulars of Premises ────────────────────────────────
    elements.append(Paragraph("PART I — PARTICULARS OF PREMISES 第一部份 — 物業資料", styles["Section"]))

    elements.append(_field_row("Address (English):", address))
    if address_zh:
        elements.append(_field_row("Address (Chinese):", address_zh))

    elements.append(Spacer(1, 3 * mm))

    # ── Part II: Particulars of Tenancy ────────────────────────────────
    elements.append(Paragraph("PART II — PARTICULARS OF TENANCY 第二部份 — 租賃資料", styles["Section"]))

    elements.append(_field_row("Commencement Date:", str(start)))
    elements.append(_field_row("Expiry Date:", str(end)))
    elements.append(_field_row("Term (months):", str(term)))
    elements.append(_field_row("Monthly Rent (HK$):", f"{rent:,}" if rent else ""))
    if stamp_duty:
        elements.append(_field_row("Stamp Duty (HK$):", f"{stamp_duty:,}" if isinstance(stamp_duty, (int, float)) else str(stamp_duty)))

    elements.append(Spacer(1, 3 * mm))

    # ── Part III: Landlord ─────────────────────────────────────────────
    elements.append(Paragraph("PART III — PARTICULARS OF LANDLORD 第三部份 — 業主資料", styles["Section"]))

    elements.append(_field_row("Name:", landlord))
    elements.append(_field_row("HKID / Passport:", landlord_hkid))
    elements.append(_field_row("Contact Number:", landlord_phone))

    elements.append(Spacer(1, 3 * mm))

    # ── Part IV: Tenant ────────────────────────────────────────────────
    elements.append(Paragraph("PART IV — PARTICULARS OF TENANT 第四部份 — 租客資料", styles["Section"]))

    elements.append(_field_row("Name:", tenant))
    elements.append(_field_row("HKID / Passport:", tenant_hkid))
    elements.append(_field_row("Contact Number:", tenant_phone))

    elements.append(Spacer(1, 8 * mm))

    # ── Declaration ────────────────────────────────────────────────────
    elements.append(Paragraph("DECLARATION 聲明", styles["Section"]))
    decl_text = (
        "I/We hereby give notice that the above premises has/have been let "
        "and confirm that the particulars given above are true and correct."
        "<br/>"
        "本人/吾等謹此通知上述物業已出租，並確認以上資料真確無誤。"
    )
    elements.append(Paragraph(decl_text, styles["Normal"]))
    elements.append(Spacer(1, 5 * mm))

    elements.append(Paragraph(
        "<b>WARNING 警告:</b> Any person who, without reasonable excuse, "
        "fails to give notice under Section 45(2) commits an offence and is "
        "liable on conviction to a fine at Level 2 (HK$5,000)."
        "<br/>"
        "任何人無合理辯解而未有根據第45(2)條發出通知，即屬犯罪，一經定罪，"
        "可處第2級罰款（港幣$5,000）。",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 8 * mm))

    # ── Signature Blocks ───────────────────────────────────────────────
    sig_data = [
        [
            f"Landlord 業主: {landlord}\n\n"
            "Signature 簽署:\n\n"
            "____________________________\n\n"
            f"Date 日期: ____________________",
            f"Tenant 租客: {tenant}\n\n"
            "Signature 簽署:\n\n"
            "____________________________\n\n"
            f"Date 日期: ____________________",
        ]
    ]
    sig = Table(sig_data, colWidths=[85 * mm, 85 * mm])
    sig.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(sig)

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "This form must be submitted within ONE MONTH of the commencement "
        "of the tenancy.",
        ParagraphStyle(
            "RedNote", parent=styles["Normal"],
            fontSize=9, textColor=colors.red,
        ),
    ))
    elements.append(Paragraph(
        "本通知書須於租賃開始後一個月內提交。",
        ParagraphStyle(
            "RedNoteZh", parent=styles["Normal"],
            fontSize=9, textColor=colors.red,
        ),
    ))

    doc.build(elements)
    return path
