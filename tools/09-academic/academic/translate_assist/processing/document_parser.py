"""PDF and DOCX text extraction with structure detection."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path


def parse_pdf(file_path: str | Path) -> list[dict]:
    """Extract text with structure from a PDF file.

    Uses PyMuPDF (fitz) to extract text page by page, attempting to detect
    section headings from font size and formatting cues.

    Args:
        file_path: Path to the PDF file.

    Returns:
        List of dicts with keys: section_name, text, page_number.
    """
    import fitz

    doc = fitz.open(str(file_path))
    segments: list[dict] = []
    current_section = "Untitled"
    current_text_parts: list[str] = []
    current_page = 1

    for page_num in range(len(doc)):
        page = doc[page_num]
        blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]

        for block in blocks:
            if block.get("type") != 0:
                continue

            for line in block.get("lines", []):
                line_text = ""
                max_font_size = 0.0
                is_bold = False

                for span in line.get("spans", []):
                    line_text += span.get("text", "")
                    size = span.get("size", 0.0)
                    if size > max_font_size:
                        max_font_size = size
                    flags = span.get("flags", 0)
                    if flags & (1 << 4):
                        is_bold = True

                stripped = line_text.strip()
                if not stripped:
                    continue

                if _looks_like_heading(stripped, max_font_size, is_bold):
                    if current_text_parts:
                        segments.append({
                            "section_name": current_section,
                            "text": "\n".join(current_text_parts).strip(),
                            "page_number": current_page,
                        })
                        current_text_parts = []
                    current_section = stripped
                    current_page = page_num + 1
                else:
                    current_text_parts.append(stripped)

    if current_text_parts:
        segments.append({
            "section_name": current_section,
            "text": "\n".join(current_text_parts).strip(),
            "page_number": current_page,
        })

    doc.close()

    if not segments:
        doc2 = fitz.open(str(file_path))
        for page_num in range(len(doc2)):
            page = doc2[page_num]
            text = page.get_text().strip()
            if text:
                segments.append({
                    "section_name": f"Page {page_num + 1}",
                    "text": text,
                    "page_number": page_num + 1,
                })
        doc2.close()

    return segments


def _looks_like_heading(text: str, font_size: float, is_bold: bool) -> bool:
    """Heuristic to determine if a line is a section heading."""
    if len(text) > 120 or len(text) < 2:
        return False

    heading_patterns = re.compile(
        r"^(?:\d+\.?\s+)?"
        r"(?:Abstract|Introduction|Background|Methods?|Methodology|Results?|"
        r"Discussion|Conclusion|References|Acknowledgements?|Appendix|"
        r"Literature Review|Findings|Analysis|"
        r"摘要|引言|背景|研究方法|方法|結果|討論|結論|參考文獻|致謝|附錄)",
        re.IGNORECASE,
    )
    if heading_patterns.match(text):
        return True

    if is_bold and font_size >= 12.0 and len(text) < 80:
        return True

    if re.match(r"^\d+\.\s+[A-Z]", text) and len(text) < 80:
        return True

    return False


def parse_docx(file_path: str | Path) -> list[dict]:
    """Extract text with headings from a DOCX file.

    Uses python-docx to iterate paragraphs, grouping text under headings.

    Args:
        file_path: Path to the DOCX file.

    Returns:
        List of dicts with keys: section_name, text.
    """
    from docx import Document

    doc = Document(str(file_path))
    segments: list[dict] = []
    current_section = "Untitled"
    current_text_parts: list[str] = []

    for para in doc.paragraphs:
        style_name = (para.style.name or "").lower()
        text = para.text.strip()

        if not text:
            continue

        if "heading" in style_name or style_name.startswith("title"):
            if current_text_parts:
                segments.append({
                    "section_name": current_section,
                    "text": "\n".join(current_text_parts).strip(),
                })
                current_text_parts = []
            current_section = text
        else:
            current_text_parts.append(text)

    if current_text_parts:
        segments.append({
            "section_name": current_section,
            "text": "\n".join(current_text_parts).strip(),
        })

    return segments


def detect_language(text: str) -> str:
    """Detect if text is English, Traditional Chinese, or Simplified Chinese.

    Uses Unicode character analysis. For Chinese text, distinguishes TC/SC
    by checking for characters unique to Traditional Chinese.

    Args:
        text: Input text to analyse.

    Returns:
        Language code: 'en', 'tc', or 'sc'.
    """
    if not text or not text.strip():
        return "en"

    cjk_count = 0
    latin_count = 0
    tc_indicators = 0
    total = 0

    tc_chars = set("國學說開關書長門問題馬東車區從點對電話過這還進遠連運過選達遲邊際隨雜難電點體齊齒龍龜")

    for ch in text:
        if ch.isspace() or ch in ".,;:!?\"'()[]{}":
            continue
        total += 1
        cat = unicodedata.category(ch)
        if cat.startswith("Lo"):
            cjk_count += 1
            if ch in tc_chars:
                tc_indicators += 1
        elif cat.startswith("L"):
            latin_count += 1

    if total == 0:
        return "en"

    if cjk_count / total > 0.3:
        if cjk_count > 0 and tc_indicators / cjk_count > 0.05:
            return "tc"
        return "sc"

    return "en"
