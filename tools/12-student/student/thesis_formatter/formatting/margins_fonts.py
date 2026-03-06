"""Apply margins, fonts, and line spacing to thesis documents."""

from __future__ import annotations

from docx import Document
from docx.shared import Mm, Pt
from docx.enum.text import WD_LINE_SPACING


def apply_margins(doc: Document, profile: dict) -> None:
    margins = profile.get("margins", {})
    if isinstance(margins, str):
        import json
        margins = json.loads(margins)

    top = margins.get("top", profile.get("margin_top", 25))
    bottom = margins.get("bottom", profile.get("margin_bottom", 25))
    left = margins.get("left", profile.get("margin_left", 25))
    right = margins.get("right", profile.get("margin_right", 25))

    for section in doc.sections:
        section.top_margin = Mm(top)
        section.bottom_margin = Mm(bottom)
        section.left_margin = Mm(left)
        section.right_margin = Mm(right)


def apply_fonts(doc: Document, profile: dict) -> None:
    font_name = profile.get("font_name", "Times New Roman")
    font_size = profile.get("font_size", 12)

    style = doc.styles["Normal"]
    style.font.name = font_name
    style.font.size = Pt(font_size)

    for para in doc.paragraphs:
        for run in para.runs:
            if run.font.name is None:
                run.font.name = font_name
            if run.font.size is None:
                run.font.size = Pt(font_size)


def apply_line_spacing(doc: Document, profile: dict) -> None:
    spacing = profile.get("line_spacing", 1.5)

    for para in doc.paragraphs:
        pf = para.paragraph_format
        if spacing == 2.0:
            pf.line_spacing_rule = WD_LINE_SPACING.DOUBLE
        elif spacing == 1.5:
            pf.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
        else:
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            pf.line_spacing = spacing
