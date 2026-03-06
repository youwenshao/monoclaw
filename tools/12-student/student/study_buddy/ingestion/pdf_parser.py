"""PDF document parser using PyMuPDF (fitz)."""

from __future__ import annotations

import fitz


def parse_pdf(file_path: str) -> list[dict]:
    doc = fitz.open(file_path)
    pages: list[dict] = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        section_title = ""
        for block in blocks:
            if "lines" not in block:
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["size"] >= 14 and span["text"].strip():
                        section_title = span["text"].strip()
                        break
                if section_title:
                    break
            if section_title:
                break

        text = page.get_text("text").strip()
        if text:
            pages.append({
                "page_number": page_num + 1,
                "text": text,
                "section_title": section_title,
            })

    doc.close()
    return pages
