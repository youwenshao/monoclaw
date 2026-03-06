"""Generate a property inventory checklist as a PDF.

Room-by-room checklist with condition notes, appliance serial numbers,
and signature blocks for landlord and tenant confirmation.
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
    PageBreak,
)


def _build_room_table(room: dict) -> list:
    """Build a table of items for a single room."""
    elements: list = []
    styles = getSampleStyleSheet()

    room_name = room.get("name", "Room")
    room_name_zh = room.get("name_zh", "")
    header_text = f"{room_name}"
    if room_name_zh:
        header_text += f"  {room_name_zh}"

    elements.append(Paragraph(header_text, styles["Heading2"]))
    elements.append(Spacer(1, 3 * mm))

    col_headers = [
        "Item 項目",
        "Qty 數量",
        "Condition 狀況",
        "Serial No. 編號",
        "Notes 備註",
    ]
    data = [col_headers]

    items = room.get("items", [])
    if not items:
        items = _default_items_for(room_name)

    for item in items:
        if isinstance(item, str):
            data.append([item, "1", "Good 良好", "", ""])
        else:
            data.append([
                item.get("name", ""),
                str(item.get("qty", 1)),
                item.get("condition", "Good 良好"),
                item.get("serial_number", ""),
                item.get("notes", ""),
            ])

    col_widths = [55 * mm, 18 * mm, 35 * mm, 35 * mm, 40 * mm]
    table = Table(data, colWidths=col_widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ALIGN", (1, 0), (1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    elements.append(table)
    elements.append(Spacer(1, 8 * mm))
    return elements


def _default_items_for(room_name: str) -> list[str]:
    """Provide sensible defaults when no items list is given."""
    lower = room_name.lower()
    if "kitchen" in lower:
        return [
            "Refrigerator 雪櫃", "Oven / Microwave 焗爐/微波爐", "Cooker Hob 爐頭",
            "Extractor Hood 抽油煙機", "Sink & Tap 洗碗盆及水龍頭",
            "Kitchen Cabinets 廚櫃", "Countertop 枱面",
        ]
    if "bathroom" in lower or "toilet" in lower:
        return [
            "Toilet Bowl 座廁", "Wash Basin 洗面盆", "Mirror 鏡",
            "Shower Head 花灑頭", "Bathtub 浴缸", "Exhaust Fan 抽氣扇",
            "Towel Rail 毛巾架",
        ]
    if "living" in lower or "lounge" in lower:
        return [
            "Sofa 沙發", "TV 電視", "Coffee Table 茶几",
            "Air Conditioner 冷氣機", "Curtains 窗簾", "Light Fixtures 燈具",
            "Walls & Ceiling 牆壁及天花",
        ]
    if "bed" in lower or "master" in lower:
        return [
            "Bed Frame 床架", "Mattress 床褥", "Wardrobe 衣櫃",
            "Air Conditioner 冷氣機", "Curtains 窗簾", "Light Fixtures 燈具",
            "Walls & Ceiling 牆壁及天花", "Windows & Locks 窗戶及鎖",
        ]
    return [
        "Air Conditioner 冷氣機", "Light Fixtures 燈具",
        "Walls & Ceiling 牆壁及天花", "Windows & Locks 窗戶及鎖",
        "Flooring 地板", "Power Sockets 電源插座",
    ]


def generate_inventory_checklist(
    tenancy_data: dict,
    rooms: list[dict],
    output_dir: Path,
) -> Path:
    """Create a property inventory checklist PDF.

    Parameters
    ----------
    tenancy_data:
        Must contain ``property_address``, ``landlord_name``, ``tenant_name``.
    rooms:
        List of dicts each having ``name`` (required) and optionally
        ``name_zh``, ``items`` (list of dicts or strings).
    output_dir:
        Directory where the PDF will be saved.

    Returns
    -------
    Path to the generated PDF file.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = (
        f"inventory_{tenancy_data.get('id', 'draft')}_"
        f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    )
    path = output_dir / filename

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "SmallGrey",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
    ))

    elements: list = []

    # ── Header ─────────────────────────────────────────────────────────
    elements.append(Paragraph(
        "PROPERTY INVENTORY CHECKLIST 物業清點表", styles["Title"]
    ))
    elements.append(Spacer(1, 5 * mm))

    address = tenancy_data.get("property_address", "")
    landlord = tenancy_data.get("landlord_name", "")
    tenant = tenancy_data.get("tenant_name", "")
    date_str = datetime.now().strftime("%d %B %Y")

    info_data = [
        ["Property 物業:", address],
        ["Landlord 業主:", landlord],
        ["Tenant 租客:", tenant],
        ["Date 日期:", date_str],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, 130 * mm])
    info_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8 * mm))

    elements.append(Paragraph(
        "Please check each item and note its condition. Both parties should "
        "sign at the end to confirm agreement.",
        styles["Normal"],
    ))
    elements.append(Paragraph(
        "請逐項檢查並記錄狀況。雙方須於末頁簽署確認。",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 6 * mm))

    # ── Room sections ──────────────────────────────────────────────────
    if not rooms:
        rooms = [
            {"name": "Living Room", "name_zh": "客廳"},
            {"name": "Kitchen", "name_zh": "廚房"},
            {"name": "Master Bedroom", "name_zh": "主人房"},
            {"name": "Bathroom", "name_zh": "浴室"},
        ]

    for room in rooms:
        elements.extend(_build_room_table(room))

    # ── General Condition ──────────────────────────────────────────────
    elements.append(Paragraph("GENERAL CONDITION 整體狀況", styles["Heading2"]))
    elements.append(Spacer(1, 3 * mm))

    general_items = [
        ["Item 項目", "Condition 狀況", "Notes 備註"],
        ["Front Door & Lock 大門及鎖", "", ""],
        ["Electricity Meter Reading 電錶讀數", "", ""],
        ["Water Meter Reading 水錶讀數", "", ""],
        ["Gas Meter Reading 煤氣錶讀數", "", ""],
        ["Keys Handed Over 交付鎖匙", "", "Number 數目:"],
        ["Access Cards 門禁卡", "", "Number 數目:"],
    ]
    gen_table = Table(general_items, colWidths=[65 * mm, 50 * mm, 65 * mm], repeatRows=1)
    gen_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2c3e50")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f9fc")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(gen_table)
    elements.append(Spacer(1, 10 * mm))

    # ── Additional Notes ───────────────────────────────────────────────
    elements.append(Paragraph("ADDITIONAL NOTES 其他備註", styles["Heading2"]))
    elements.append(Spacer(1, 3 * mm))
    for _ in range(5):
        elements.append(Paragraph(
            "_" * 110, styles["Normal"]
        ))
        elements.append(Spacer(1, 4 * mm))

    elements.append(Spacer(1, 10 * mm))

    # ── Signature Blocks ───────────────────────────────────────────────
    sig_data = [
        [
            f"Landlord 業主: {landlord}\n\n"
            "Signature 簽署: ____________________\n\n"
            "Date 日期: ____________________",
            f"Tenant 租客: {tenant}\n\n"
            "Signature 簽署: ____________________\n\n"
            "Date 日期: ____________________",
        ]
    ]
    sig_table = Table(sig_data, colWidths=[90 * mm, 90 * mm])
    sig_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    return path
