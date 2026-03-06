"""Apply university formatting profiles to .docx thesis documents."""

from __future__ import annotations

import shutil
from pathlib import Path

from docx import Document

from student.thesis_formatter.formatting.margins_fonts import (
    apply_fonts,
    apply_line_spacing,
    apply_margins,
)
from student.thesis_formatter.formatting.styles_manager import set_heading_styles


def apply_template(doc_path: str, profile: dict) -> str:
    output_path = _output_path(doc_path, suffix="_formatted")
    shutil.copy2(doc_path, output_path)

    doc = Document(output_path)
    apply_margins(doc, profile)
    apply_fonts(doc, profile)
    apply_line_spacing(doc, profile)
    set_heading_styles(doc, profile)
    doc.save(output_path)
    return output_path


def _output_path(doc_path: str, suffix: str = "") -> str:
    p = Path(doc_path)
    return str(p.parent / f"{p.stem}{suffix}{p.suffix}")
