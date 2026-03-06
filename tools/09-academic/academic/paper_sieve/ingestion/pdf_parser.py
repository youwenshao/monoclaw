"""Layout-aware PDF text extraction using PyMuPDF (fitz)."""

from __future__ import annotations

import logging
import re
import statistics
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF

logger = logging.getLogger("openclaw.academic.paper_sieve.pdf_parser")

_HEADING_PATTERNS = re.compile(
    r"^(?:"
    r"\d+\.?\s+"
    r"|[IVXLCDM]+\.?\s+"
    r"|[A-Z]\.?\s+"
    r")?"
    r"(?:Abstract|Introduction|Background|Related\s+Work|Methodology|Methods?"
    r"|Results?|Discussion|Conclusion|Acknowledgements?|References|Bibliography"
    r"|Appendix|Supplementary|Materials?\s+and\s+Methods?"
    r"|Literature\s+Review|Theoretical\s+Framework|Data|Analysis"
    r"|Experiment(?:s|al)?|Evaluation|Future\s+Work|Limitations)"
    r"s?$",
    re.IGNORECASE,
)


def _is_two_column(blocks: list[dict[str, Any]], page_width: float) -> bool:
    """Heuristic: if many text blocks cluster in left/right halves, assume two columns."""
    if len(blocks) < 4:
        return False
    midpoint = page_width / 2
    left_count = sum(1 for b in blocks if b["x1"] < midpoint + 20)
    right_count = sum(1 for b in blocks if b["x0"] > midpoint - 20)
    return left_count >= 2 and right_count >= 2


def _sort_blocks_two_column(
    blocks: list[dict[str, Any]], page_width: float
) -> list[dict[str, Any]]:
    """Sort blocks: left column top-to-bottom, then right column top-to-bottom."""
    midpoint = page_width / 2
    left = sorted(
        [b for b in blocks if b["x0"] < midpoint],
        key=lambda b: (b["y0"], b["x0"]),
    )
    right = sorted(
        [b for b in blocks if b["x0"] >= midpoint],
        key=lambda b: (b["y0"], b["x0"]),
    )
    return left + right


def _extract_blocks(page: fitz.Page) -> list[dict[str, Any]]:
    """Extract text blocks with position and font metadata from a single page."""
    raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
    result: list[dict[str, Any]] = []

    for block in raw_blocks:
        if block.get("type") != 0:
            continue
        lines_text: list[str] = []
        font_sizes: list[float] = []
        is_bold = False

        for line in block.get("lines", []):
            spans_text: list[str] = []
            for span in line.get("spans", []):
                spans_text.append(span["text"])
                font_sizes.append(span["size"])
                flags = span.get("flags", 0)
                if flags & 2 ** 4:
                    is_bold = True
            lines_text.append("".join(spans_text))

        text = "\n".join(lines_text).strip()
        if not text:
            continue

        bbox = block["bbox"]
        result.append({
            "text": text,
            "x0": bbox[0],
            "y0": bbox[1],
            "x1": bbox[2],
            "y1": bbox[3],
            "avg_font_size": statistics.mean(font_sizes) if font_sizes else 0,
            "max_font_size": max(font_sizes) if font_sizes else 0,
            "is_bold": is_bold,
        })

    return result


def extract_text_from_pdf(file_path: str | Path) -> list[dict[str, Any]]:
    """Extract text from a PDF with layout awareness and two-column detection.

    Returns a list of dicts, one per page:
        - page_number: 1-based page index
        - text: concatenated page text in reading order
        - blocks: list of block dicts with text, position, and font metadata
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    doc = fitz.open(str(path))
    pages: list[dict[str, Any]] = []

    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            blocks = _extract_blocks(page)
            page_width = page.rect.width

            if _is_two_column(blocks, page_width):
                blocks = _sort_blocks_two_column(blocks, page_width)

            text = "\n\n".join(b["text"] for b in blocks)
            pages.append({
                "page_number": page_idx + 1,
                "text": text,
                "blocks": blocks,
            })
    finally:
        doc.close()

    return pages


def detect_sections(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Detect section headings by font size, bold flags, and known heading patterns.

    Returns a list of dicts:
        - section_name: detected heading text
        - start_page: 1-based page number where this section begins
        - text: full text belonging to this section (until the next heading)
    """
    if not pages:
        return []

    all_font_sizes: list[float] = []
    for page in pages:
        for block in page.get("blocks", []):
            if block["avg_font_size"] > 0:
                all_font_sizes.append(block["avg_font_size"])

    body_size = statistics.median(all_font_sizes) if all_font_sizes else 10.0
    heading_threshold = body_size * 1.15

    flat_blocks: list[tuple[int, dict[str, Any]]] = []
    for page in pages:
        for block in page.get("blocks", []):
            flat_blocks.append((page["page_number"], block))

    sections: list[dict[str, Any]] = []
    current_name = "Preamble"
    current_page = 1
    current_texts: list[str] = []

    for page_num, block in flat_blocks:
        text = block["text"].strip()
        lines = text.split("\n")
        first_line = lines[0].strip() if lines else ""

        is_heading = False
        if block["max_font_size"] >= heading_threshold and len(first_line) < 100:
            is_heading = True
        elif block["is_bold"] and len(first_line) < 100 and _HEADING_PATTERNS.match(first_line):
            is_heading = True
        elif _HEADING_PATTERNS.match(first_line) and first_line.isupper():
            is_heading = True

        if is_heading and first_line:
            if current_texts or sections:
                sections.append({
                    "section_name": current_name,
                    "start_page": current_page,
                    "text": "\n\n".join(current_texts),
                })
            current_name = first_line
            current_page = page_num
            remaining = "\n".join(lines[1:]).strip()
            current_texts = [remaining] if remaining else []
        else:
            current_texts.append(text)

    if current_texts:
        sections.append({
            "section_name": current_name,
            "start_page": current_page,
            "text": "\n\n".join(current_texts),
        })

    return sections
