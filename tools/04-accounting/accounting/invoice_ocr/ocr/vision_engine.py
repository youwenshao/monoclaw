"""macOS Vision framework OCR wrapper for invoice processing."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.accounting.ocr.vision")


def process_image(file_path: str, language_hints: list[str] | None = None) -> dict[str, Any]:
    """Run macOS Vision OCR on an image file and return structured text blocks."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {file_path}")

    if language_hints is None:
        language_hints = ["en", "zh-Hant", "zh-Hans"]

    try:
        import Vision
        import Quartz

        image_url = Quartz.NSURL.fileURLWithPath_(str(path))
        image_source = Quartz.CGImageSourceCreateWithURL(image_url, None)
        if image_source is None:
            raise RuntimeError(f"Cannot load image: {file_path}")
        cg_image = Quartz.CGImageSourceCreateImageAtIndex(image_source, 0, None)

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(language_hints)
        request.setUsesLanguageCorrection_(True)

        handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(cg_image, None)
        success = handler.performRequests_error_([request], None)

        if not success[0]:
            logger.warning("Vision OCR returned no results for %s", file_path)
            return {"raw_text": "", "blocks": [], "confidence": 0.0}

        blocks = []
        full_text_parts = []
        for observation in request.results():
            candidate = observation.topCandidates_(1)[0]
            text = candidate.string()
            confidence = candidate.confidence()
            bbox = observation.boundingBox()
            blocks.append({
                "text": text,
                "confidence": float(confidence),
                "bbox": {
                    "x": float(bbox.origin.x),
                    "y": float(bbox.origin.y),
                    "width": float(bbox.size.width),
                    "height": float(bbox.size.height),
                },
            })
            full_text_parts.append(text)

        avg_confidence = sum(b["confidence"] for b in blocks) / len(blocks) if blocks else 0.0

        return {
            "raw_text": "\n".join(full_text_parts),
            "blocks": blocks,
            "confidence": round(avg_confidence, 4),
        }

    except ImportError:
        logger.warning("macOS Vision framework not available, returning mock OCR result")
        return _mock_ocr(file_path)


def _mock_ocr(file_path: str) -> dict[str, Any]:
    """Fallback mock OCR for non-macOS environments."""
    return {
        "raw_text": (
            "INVOICE\n"
            "Supplier: Demo Supplier Ltd\n"
            "Invoice No: INV-001\n"
            "Date: 2026-03-01\n"
            "Due Date: 2026-04-01\n"
            "\n"
            "Description          Qty   Unit Price   Amount\n"
            "Consulting Services   10      500.00   5,000.00\n"
            "Travel Expenses        1    1,000.00   1,000.00\n"
            "\n"
            "Subtotal: HKD 6,000.00\n"
            "Tax (0%): HKD 0.00\n"
            "Total: HKD 6,000.00"
        ),
        "blocks": [
            {"text": "INVOICE", "confidence": 0.95, "bbox": {"x": 0.1, "y": 0.9, "width": 0.3, "height": 0.05}},
            {"text": "Supplier: Demo Supplier Ltd", "confidence": 0.92, "bbox": {"x": 0.1, "y": 0.85, "width": 0.6, "height": 0.04}},
            {"text": "Invoice No: INV-001", "confidence": 0.90, "bbox": {"x": 0.1, "y": 0.80, "width": 0.4, "height": 0.04}},
            {"text": "Date: 2026-03-01", "confidence": 0.93, "bbox": {"x": 0.1, "y": 0.75, "width": 0.3, "height": 0.04}},
            {"text": "Due Date: 2026-04-01", "confidence": 0.93, "bbox": {"x": 0.5, "y": 0.75, "width": 0.3, "height": 0.04}},
            {"text": "Consulting Services   10   500.00   5,000.00", "confidence": 0.88, "bbox": {"x": 0.1, "y": 0.55, "width": 0.8, "height": 0.04}},
            {"text": "Travel Expenses   1   1,000.00   1,000.00", "confidence": 0.87, "bbox": {"x": 0.1, "y": 0.50, "width": 0.8, "height": 0.04}},
            {"text": "Subtotal: HKD 6,000.00", "confidence": 0.91, "bbox": {"x": 0.5, "y": 0.3, "width": 0.4, "height": 0.04}},
            {"text": "Tax (0%): HKD 0.00", "confidence": 0.90, "bbox": {"x": 0.5, "y": 0.25, "width": 0.4, "height": 0.04}},
            {"text": "Total: HKD 6,000.00", "confidence": 0.91, "bbox": {"x": 0.5, "y": 0.2, "width": 0.4, "height": 0.04}},
        ],
        "confidence": 0.91,
    }
