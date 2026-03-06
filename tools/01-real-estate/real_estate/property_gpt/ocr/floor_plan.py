"""Floor-plan OCR using the macOS Vision framework (via pyobjc).

Falls back gracefully on non-macOS platforms or when pyobjc is not installed.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def extract_floor_plan(image_path: str | Path) -> dict[str, Any]:
    """Extract structured data from a floor-plan image.

    Uses macOS Vision framework for text recognition, then parses the
    recognised strings into a structured JSON-like dict containing room
    names, dimensions, and total saleable area when available.

    Returns a dict with keys:
        rooms   — list of {name, area_sqft} dicts
        raw_text — full OCR text
        saleable_area_sqft — parsed saleable area or None
        error   — error message if OCR failed
    """
    image_path = Path(image_path)
    if not image_path.exists():
        return {"error": f"Image not found: {image_path}", "rooms": [], "raw_text": ""}

    try:
        return _ocr_with_vision(image_path)
    except ImportError:
        logger.warning("pyobjc not available — Vision OCR disabled")
        return {
            "error": "macOS Vision framework not available (pyobjc not installed)",
            "rooms": [],
            "raw_text": "",
            "saleable_area_sqft": None,
        }
    except Exception as exc:
        logger.exception("Floor-plan OCR failed")
        return {"error": str(exc), "rooms": [], "raw_text": "", "saleable_area_sqft": None}


def _ocr_with_vision(image_path: Path) -> dict[str, Any]:
    """Run Apple Vision text recognition on *image_path*."""
    import Quartz
    import Vision

    image_url = Quartz.CFURLCreateWithFileSystemPath(
        None, str(image_path), Quartz.kCFURLPOSIXPathStyle, False,
    )
    image_source = Quartz.CGImageSourceCreateWithURL(image_url, None)
    cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

    if cg_image is None:
        return {"error": "Failed to load image via CoreGraphics", "rooms": [], "raw_text": ""}

    request = Vision.VNRecognizeTextRequest.alloc().init()
    request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    request.setRecognitionLanguages_(["en", "zh-Hant"])

    handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
    success = handler.performRequests_error_([request], None)
    if not success[0]:
        return {"error": "Vision request failed", "rooms": [], "raw_text": ""}

    observations = request.results()
    lines: list[str] = []
    for obs in observations or []:
        candidate = obs.topCandidates_(1)
        if candidate:
            lines.append(candidate[0].string())

    raw_text = "\n".join(lines)
    rooms = _parse_rooms(raw_text)
    saleable = _parse_saleable_area(raw_text)

    return {
        "rooms": rooms,
        "raw_text": raw_text,
        "saleable_area_sqft": saleable,
        "error": None,
    }


_ROOM_PATTERN = re.compile(
    r"(?P<name>(?:bed\s?room|living|kitchen|bathroom|bath|balcony|utility|dining|master|store|"
    r"客廳|睡房|廚房|浴室|露台|工人房|飯廳))\s*[:\-]?\s*(?P<area>[\d,.]+)\s*(?:sq\.?\s*ft|呎)",
    re.IGNORECASE,
)

_SALEABLE_PATTERN = re.compile(
    r"saleable\s*(?:area)?\s*[:\-]?\s*(?P<area>[\d,.]+)\s*(?:sq\.?\s*ft|呎)",
    re.IGNORECASE,
)


def _parse_rooms(text: str) -> list[dict[str, Any]]:
    rooms: list[dict[str, Any]] = []
    for m in _ROOM_PATTERN.finditer(text):
        area_str = m.group("area").replace(",", "")
        try:
            area = float(area_str)
        except ValueError:
            area = None
        rooms.append({"name": m.group("name").strip(), "area_sqft": area})
    return rooms


def _parse_saleable_area(text: str) -> float | None:
    m = _SALEABLE_PATTERN.search(text)
    if not m:
        return None
    try:
        return float(m.group("area").replace(",", ""))
    except ValueError:
        return None
