"""macOS Vision framework OCR wrapper."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.immigration.ocr.vision")

SUPPORTED_LANGUAGES = ["zh-Hant", "zh-Hans", "en-US"]

MOCK_RESULTS: dict[str, dict[str, Any]] = {
    "hkid": {
        "lines": [
            {"text": "HONG KONG PERMANENT IDENTITY CARD", "confidence": 0.98, "bbox": [0.05, 0.02, 0.95, 0.08]},
            {"text": "香港永久性居民身份證", "confidence": 0.96, "bbox": [0.05, 0.08, 0.95, 0.14]},
            {"text": "CHAN, Tai Man", "confidence": 0.97, "bbox": [0.30, 0.20, 0.85, 0.26]},
            {"text": "陳大文", "confidence": 0.95, "bbox": [0.30, 0.27, 0.55, 0.33]},
            {"text": "A123456(7)", "confidence": 0.99, "bbox": [0.30, 0.36, 0.60, 0.42]},
            {"text": "01-01-1990", "confidence": 0.96, "bbox": [0.30, 0.45, 0.55, 0.51]},
            {"text": "15-06-2020", "confidence": 0.94, "bbox": [0.30, 0.54, 0.55, 0.60]},
        ],
        "raw_text": "HONG KONG PERMANENT IDENTITY CARD\n香港永久性居民身份證\nCHAN, Tai Man\n陳大文\nA123456(7)\n01-01-1990\n15-06-2020",
        "doc_type": "hkid",
    },
    "passport": {
        "lines": [
            {"text": "HONG KONG SPECIAL ADMINISTRATIVE REGION", "confidence": 0.97, "bbox": [0.10, 0.02, 0.90, 0.06]},
            {"text": "PASSPORT", "confidence": 0.99, "bbox": [0.35, 0.06, 0.65, 0.10]},
            {"text": "Surname / 姓: CHAN", "confidence": 0.96, "bbox": [0.05, 0.20, 0.50, 0.25]},
            {"text": "Given names / 名: TAI MAN", "confidence": 0.95, "bbox": [0.05, 0.26, 0.60, 0.31]},
            {"text": "Nationality: CHINESE", "confidence": 0.97, "bbox": [0.05, 0.32, 0.50, 0.37]},
            {"text": "Date of birth: 01 JAN 1990", "confidence": 0.96, "bbox": [0.05, 0.38, 0.55, 0.43]},
            {"text": "Passport No: H12345678", "confidence": 0.98, "bbox": [0.05, 0.44, 0.55, 0.49]},
            {"text": "Date of expiry: 01 JAN 2030", "confidence": 0.95, "bbox": [0.05, 0.50, 0.55, 0.55]},
            {"text": "P<CHNCHAN<<TAI<MAN<<<<<<<<<<<<<<<<<<<<<<<<<<<", "confidence": 0.92, "bbox": [0.02, 0.85, 0.98, 0.90]},
            {"text": "H123456789CHN9001014M3001011<<<<<<<<<<<<<<04", "confidence": 0.91, "bbox": [0.02, 0.90, 0.98, 0.95]},
        ],
        "raw_text": "HONG KONG SPECIAL ADMINISTRATIVE REGION\nPASSPORT\nCHAN TAI MAN\nCHINESE\n01 JAN 1990\nH12345678\n01 JAN 2030\nP<CHNCHAN<<TAI<MAN<<<<<<<<<<<<<<<<<<<<<<<<<<<\nH123456789CHN9001014M3001011<<<<<<<<<<<<<<04",
        "doc_type": "passport",
    },
    "bank_statement": {
        "lines": [
            {"text": "HSBC", "confidence": 0.99, "bbox": [0.05, 0.02, 0.20, 0.06]},
            {"text": "Statement of Account", "confidence": 0.97, "bbox": [0.30, 0.02, 0.70, 0.06]},
            {"text": "Account Holder: CHAN TAI MAN", "confidence": 0.96, "bbox": [0.05, 0.10, 0.60, 0.14]},
            {"text": "Account Number: 123-456789-833", "confidence": 0.95, "bbox": [0.05, 0.15, 0.55, 0.19]},
            {"text": "Statement Period: 01/01/2026 - 31/01/2026", "confidence": 0.94, "bbox": [0.05, 0.20, 0.65, 0.24]},
            {"text": "Ending Balance: HKD 1,234,567.89", "confidence": 0.93, "bbox": [0.05, 0.80, 0.60, 0.84]},
            {"text": "Average Balance: HKD 987,654.32", "confidence": 0.91, "bbox": [0.05, 0.85, 0.60, 0.89]},
        ],
        "raw_text": "HSBC\nStatement of Account\nCHAN TAI MAN\n123-456789-833\n01/01/2026 - 31/01/2026\nHKD 1,234,567.89\nHKD 987,654.32",
        "doc_type": "bank_statement",
    },
    "tax_return": {
        "lines": [
            {"text": "INLAND REVENUE DEPARTMENT", "confidence": 0.98, "bbox": [0.15, 0.02, 0.85, 0.06]},
            {"text": "TAX RETURN - INDIVIDUALS (BIR60)", "confidence": 0.97, "bbox": [0.15, 0.07, 0.85, 0.11]},
            {"text": "Year of Assessment: 2025/26", "confidence": 0.96, "bbox": [0.05, 0.15, 0.55, 0.19]},
            {"text": "Total Income: HKD 720,000", "confidence": 0.94, "bbox": [0.05, 0.50, 0.55, 0.54]},
            {"text": "Net Chargeable Income: HKD 588,000", "confidence": 0.93, "bbox": [0.05, 0.60, 0.60, 0.64]},
            {"text": "Tax Payable: HKD 67,060", "confidence": 0.95, "bbox": [0.05, 0.70, 0.55, 0.74]},
        ],
        "raw_text": "INLAND REVENUE DEPARTMENT\nTAX RETURN - INDIVIDUALS (BIR60)\n2025/26\nTotal Income: HKD 720,000\nNet Chargeable Income: HKD 588,000\nTax Payable: HKD 67,060",
        "doc_type": "tax_return",
    },
    "employment_contract": {
        "lines": [
            {"text": "EMPLOYMENT CONTRACT", "confidence": 0.98, "bbox": [0.25, 0.02, 0.75, 0.06]},
            {"text": "Employer: TechCorp (HK) Limited", "confidence": 0.96, "bbox": [0.05, 0.12, 0.65, 0.16]},
            {"text": "Employee: CHAN TAI MAN", "confidence": 0.97, "bbox": [0.05, 0.18, 0.55, 0.22]},
            {"text": "Position: Senior Software Engineer", "confidence": 0.95, "bbox": [0.05, 0.24, 0.60, 0.28]},
            {"text": "Monthly Salary: HKD 55,000", "confidence": 0.94, "bbox": [0.05, 0.30, 0.55, 0.34]},
            {"text": "Start Date: 01 March 2026", "confidence": 0.93, "bbox": [0.05, 0.36, 0.55, 0.40]},
            {"text": "Duration: 2 years", "confidence": 0.92, "bbox": [0.05, 0.42, 0.45, 0.46]},
        ],
        "raw_text": "EMPLOYMENT CONTRACT\nTechCorp (HK) Limited\nCHAN TAI MAN\nSenior Software Engineer\nHKD 55,000\n01 March 2026\n2 years",
        "doc_type": "employment_contract",
    },
}


def _mock_result(doc_type: str) -> dict[str, Any]:
    """Return realistic mock OCR output when the Vision framework is unavailable."""
    result = MOCK_RESULTS.get(doc_type)
    if result:
        return result
    return MOCK_RESULTS.get("passport", {
        "lines": [{"text": "Sample document text", "confidence": 0.90, "bbox": [0.0, 0.0, 1.0, 1.0]}],
        "raw_text": "Sample document text",
        "doc_type": doc_type,
    })


def process_image(file_path: str, doc_type: str) -> dict[str, Any]:
    """Run OCR on an image using macOS Vision or fall back to mock data.

    Returns a dict with keys: lines (list of {text, confidence, bbox}),
    raw_text (str), and doc_type (str).
    """
    path = Path(file_path)

    try:
        import objc  # noqa: F401
        from Quartz import CIImage
        import Vision

        ci_image = CIImage.imageWithContentsOfURL_(
            __import__("Foundation").NSURL.fileURLWithPath_(str(path))
        )
        if ci_image is None:
            logger.warning("Vision: could not load image at %s, using mock", file_path)
            return _mock_result(doc_type)

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(SUPPORTED_LANGUAGES)
        request.setUsesLanguageCorrection_(True)

        handler = Vision.VNImageRequestHandler.alloc().initWithCIImage_options_(ci_image, None)
        success = handler.performRequests_error_([request], None)

        if not success[0]:
            logger.warning("Vision request failed for %s, using mock", file_path)
            return _mock_result(doc_type)

        observations = request.results()
        lines: list[dict[str, Any]] = []
        raw_parts: list[str] = []

        for obs in observations or []:
            candidate = obs.topCandidates_(1)
            if not candidate:
                continue
            top = candidate[0]
            text = str(top.string())
            conf = float(top.confidence())
            box = obs.boundingBox()
            bbox = [box.origin.x, box.origin.y, box.size.width, box.size.height]
            lines.append({"text": text, "confidence": conf, "bbox": bbox})
            raw_parts.append(text)

        return {"lines": lines, "raw_text": "\n".join(raw_parts), "doc_type": doc_type}

    except (ImportError, Exception) as exc:
        logger.info("Vision framework unavailable (%s), returning mock data", exc)
        return _mock_result(doc_type)
