"""PDF generation — overlay form field values onto ImmD templates."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.immigration.form_autofill.overlay")


def generate_pdf(
    form_type: str,
    field_values: dict[str, Any],
    output_dir: Path,
) -> Path:
    """Generate a filled PDF for *form_type* with the supplied field values.

    If a background template exists in ``output_dir / ../templates/<form_type>.pdf``,
    the overlay is merged on top of it.  Otherwise a standalone PDF is created.

    Returns the path to the generated file.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas as rl_canvas

    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    overlay_path = output_dir / f"{form_type}_{timestamp}_overlay.pdf"
    final_path = output_dir / f"{form_type}_{timestamp}.pdf"

    _register_cjk_font()

    from immigration.form_autofill.forms.base import get_form_definition
    form_def = get_form_definition(form_type)
    fields = form_def.get_field_list()

    page_width, page_height = A4
    c = rl_canvas.Canvas(str(overlay_path), pagesize=A4)

    pages: dict[int, list[dict]] = {}
    for field in fields:
        pages.setdefault(field["page"], []).append(field)

    for page_num in sorted(pages):
        if page_num > 1:
            c.showPage()

        y_cursor = page_height - 30 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(20 * mm, y_cursor, f"{form_def.form_name}")
        c.setFont("Helvetica", 8)
        c.drawString(20 * mm, y_cursor - 5 * mm, f"Form {form_type} — Page {page_num}")
        y_cursor -= 15 * mm

        for field in pages[page_num]:
            if y_cursor < 25 * mm:
                c.showPage()
                y_cursor = page_height - 20 * mm

            name = field["name"]
            label = field["label"]
            value = field_values.get(name, "")

            rendered = _render_value(value, field)

            c.setFont("Helvetica", 7)
            c.setFillColorRGB(0.4, 0.4, 0.4)
            c.drawString(20 * mm, y_cursor, label)

            font_name = _pick_font(rendered)
            c.setFont(font_name, 10)
            c.setFillColorRGB(0, 0, 0)
            c.drawString(20 * mm, y_cursor - 4.5 * mm, rendered)

            c.setStrokeColorRGB(0.8, 0.8, 0.8)
            c.line(20 * mm, y_cursor - 5.5 * mm, page_width - 20 * mm, y_cursor - 5.5 * mm)

            y_cursor -= 12 * mm

    c.save()
    logger.info("Overlay PDF created: %s", overlay_path)

    template_path = output_dir.parent / "templates" / f"{form_type}.pdf"
    if template_path.exists():
        _merge_pdfs(template_path, overlay_path, final_path)
        overlay_path.unlink(missing_ok=True)
    else:
        overlay_path.rename(final_path)
        logger.debug("No background template found at %s — using standalone", template_path)

    logger.info("Final PDF: %s", final_path)
    return final_path


def _render_value(value: Any, field: dict) -> str:
    """Convert a raw value to its display string."""
    if value is None or value == "":
        return ""

    str_val = str(value)

    if field["field_type"] == "checkbox":
        return "Yes" if str_val.upper() in ("Y", "1", "TRUE", "YES") else "No"

    if field["field_type"] == "text" and str_val.isascii():
        return str_val.upper()

    return str_val


def _pick_font(text: str) -> str:
    """Choose Helvetica for ASCII, CJK font for everything else."""
    if text.isascii():
        return "Helvetica"
    return "CJK" if _cjk_available() else "Helvetica"


_cjk_registered = False


def _register_cjk_font() -> None:
    """Try to register a CJK-capable font for Chinese characters."""
    global _cjk_registered
    if _cjk_registered:
        return

    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = [
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont("CJK", path, subfontIndex=0))
                _cjk_registered = True
                logger.debug("Registered CJK font from %s", path)
                return
            except Exception:
                continue

    logger.warning("No CJK font found — Chinese characters may not render correctly")


def _cjk_available() -> bool:
    return _cjk_registered


def _merge_pdfs(background: Path, overlay: Path, output: Path) -> None:
    """Merge overlay on top of background template page by page."""
    from PyPDF2 import PdfReader, PdfWriter

    bg_reader = PdfReader(str(background))
    ol_reader = PdfReader(str(overlay))
    writer = PdfWriter()

    for i in range(max(len(bg_reader.pages), len(ol_reader.pages))):
        if i < len(bg_reader.pages):
            page = bg_reader.pages[i]
            if i < len(ol_reader.pages):
                page.merge_page(ol_reader.pages[i])
            writer.add_page(page)
        elif i < len(ol_reader.pages):
            writer.add_page(ol_reader.pages[i])

    with open(output, "wb") as f:
        writer.write(f)

    logger.debug("Merged %d bg pages + %d overlay pages → %s",
                 len(bg_reader.pages), len(ol_reader.pages), output)
