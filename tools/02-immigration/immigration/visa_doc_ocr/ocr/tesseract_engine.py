"""Tesseract OCR fallback engine."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.immigration.ocr.tesseract")


def _mock_result(file_path: str, lang: str) -> dict[str, Any]:
    """Return mock results when pytesseract is not installed."""
    return {
        "lines": [
            {"text": "HONG KONG PERMANENT IDENTITY CARD", "confidence": 0.88, "bbox": [0, 0, 800, 50]},
            {"text": "CHAN, Tai Man", "confidence": 0.85, "bbox": [100, 120, 500, 160]},
            {"text": "陳大文", "confidence": 0.82, "bbox": [100, 170, 300, 210]},
            {"text": "A123456(7)", "confidence": 0.90, "bbox": [100, 220, 350, 260]},
            {"text": "01-01-1990", "confidence": 0.87, "bbox": [100, 270, 320, 310]},
        ],
        "raw_text": (
            "HONG KONG PERMANENT IDENTITY CARD\n"
            "CHAN, Tai Man\n"
            "陳大文\n"
            "A123456(7)\n"
            "01-01-1990"
        ),
        "doc_type": "unknown",
        "engine": "tesseract_mock",
        "lang": lang,
    }


def process_image_tesseract(file_path: str, lang: str = "chi_tra+eng") -> dict[str, Any]:
    """Run OCR via Tesseract or return mock data if unavailable.

    Returns dict with keys: lines, raw_text, doc_type, engine, lang.
    """
    path = Path(file_path)
    if not path.exists():
        logger.warning("File not found: %s — returning mock", file_path)
        return _mock_result(file_path, lang)

    try:
        import pytesseract
        from PIL import Image

        image = Image.open(path)
        data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)

        lines: list[dict[str, Any]] = []
        current_line: list[str] = []
        current_conf: list[float] = []
        current_bbox: list[int] = [0, 0, 0, 0]
        last_line_num = -1

        for i, text in enumerate(data["text"]):
            line_num = data["line_num"][i]
            conf = float(data["conf"][i])

            if line_num != last_line_num and current_line:
                avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0
                lines.append({
                    "text": " ".join(current_line),
                    "confidence": max(0, min(avg_conf / 100.0, 1.0)),
                    "bbox": current_bbox[:],
                })
                current_line = []
                current_conf = []
                current_bbox = [0, 0, 0, 0]

            last_line_num = line_num
            stripped = text.strip()
            if stripped and conf > 0:
                current_line.append(stripped)
                current_conf.append(conf)
                x, y, w, h = data["left"][i], data["top"][i], data["width"][i], data["height"][i]
                if not current_bbox[2]:
                    current_bbox = [x, y, x + w, y + h]
                else:
                    current_bbox[0] = min(current_bbox[0], x)
                    current_bbox[1] = min(current_bbox[1], y)
                    current_bbox[2] = max(current_bbox[2], x + w)
                    current_bbox[3] = max(current_bbox[3], y + h)

        if current_line:
            avg_conf = sum(current_conf) / len(current_conf) if current_conf else 0
            lines.append({
                "text": " ".join(current_line),
                "confidence": max(0, min(avg_conf / 100.0, 1.0)),
                "bbox": current_bbox[:],
            })

        raw_text = "\n".join(ln["text"] for ln in lines)
        return {
            "lines": lines,
            "raw_text": raw_text,
            "doc_type": "unknown",
            "engine": "tesseract",
            "lang": lang,
        }

    except ImportError:
        logger.info("pytesseract not installed — returning mock data")
        return _mock_result(file_path, lang)
    except Exception as exc:
        logger.warning("Tesseract processing failed (%s) — returning mock data", exc)
        return _mock_result(file_path, lang)
