"""Word document parser using python-docx."""

from __future__ import annotations

from docx import Document


def parse_docx(file_path: str) -> list[dict]:
    doc = Document(file_path)
    paragraphs: list[dict] = []

    for idx, para in enumerate(doc.paragraphs):
        text = para.text.strip()
        if not text:
            continue

        heading_level: int | None = None
        style_name = para.style.name if para.style else ""

        if style_name.startswith("Heading"):
            try:
                heading_level = int(style_name.split()[-1])
            except (ValueError, IndexError):
                heading_level = 1

        paragraphs.append({
            "paragraph_index": idx,
            "text": text,
            "heading_level": heading_level,
            "style": style_name,
        })

    return paragraphs
