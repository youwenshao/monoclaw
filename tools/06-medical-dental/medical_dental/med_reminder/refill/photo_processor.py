"""OCR pipeline for medication packaging photos."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.medical-dental.med_reminder.photo")


def _try_import_pil() -> Any:
    try:
        from PIL import Image, ImageEnhance  # type: ignore[import-untyped]
        return Image, ImageEnhance
    except ImportError:
        return None, None


def _try_import_tesseract() -> Any:
    try:
        import pytesseract  # type: ignore[import-untyped]
        return pytesseract
    except ImportError:
        return None


class PhotoProcessor:
    """Extract drug information from medication packaging photos via OCR."""

    MAX_DIMENSION = 1200

    def __init__(self, llm: Any | None = None) -> None:
        self._llm = llm

    def process_photo(self, image_path: str | Path) -> dict[str, Any]:
        """Run the OCR pipeline on an image.

        Returns:
            {
                "extracted_text": str,
                "drug_name": str | None,
                "confidence": float,
            }
        """
        path = Path(image_path)

        Image, ImageEnhance = _try_import_pil()
        pytesseract = _try_import_tesseract()

        if Image is None or pytesseract is None:
            return self._mock_extraction(path)

        try:
            img = Image.open(path)
            img = self._resize(img, Image)
            img = self._enhance(img, ImageEnhance)

            text_en = pytesseract.image_to_string(img, lang="eng")
            text_chi = ""
            try:
                text_chi = pytesseract.image_to_string(img, lang="chi_tra")
            except Exception:
                pass

            raw_text = f"{text_en}\n{text_chi}".strip()
            drug_name, confidence = self._extract_drug_name(raw_text)

            if confidence < 0.7 and self._llm is not None:
                llm_result = self._llm_fallback(raw_text)
                if llm_result["confidence"] > confidence:
                    drug_name = llm_result["drug_name"]
                    confidence = llm_result["confidence"]

            return {
                "extracted_text": raw_text,
                "drug_name": drug_name,
                "confidence": round(confidence, 2),
            }

        except Exception:
            logger.exception("OCR processing failed for %s", path)
            return {
                "extracted_text": "",
                "drug_name": None,
                "confidence": 0.0,
            }

    # ------------------------------------------------------------------

    def _resize(self, img: Any, Image: Any) -> Any:
        w, h = img.size
        if max(w, h) <= self.MAX_DIMENSION:
            return img
        ratio = self.MAX_DIMENSION / max(w, h)
        new_size = (int(w * ratio), int(h * ratio))
        return img.resize(new_size, Image.LANCZOS)

    @staticmethod
    def _enhance(img: Any, ImageEnhance: Any) -> Any:
        img = ImageEnhance.Contrast(img).enhance(1.5)
        img = ImageEnhance.Sharpness(img).enhance(2.0)
        return img

    @staticmethod
    def _extract_drug_name(text: str) -> tuple[str | None, float]:
        """Heuristic extraction of drug name from OCR text.

        Looks for common pharmaceutical label patterns.
        """
        if not text.strip():
            return None, 0.0

        patterns = [
            r"(?i)(?:drug\s*name|medication|藥名|藥物)[:\s]*([A-Za-z\u4e00-\u9fff][\w\s\u4e00-\u9fff]{2,30})",
            r"(?i)((?:Amlodipine|Metformin|Atorvastatin|Omeprazole|Losartan|Aspirin|Paracetamol|Ibuprofen|Amoxicillin|Warfarin|Simvastatin|Lisinopril|Atenolol|Clopidogrel|Pantoprazole)\b[\w\s]*\d*\s*mg)",
            r"(?i)([A-Z][a-z]{4,20})\s+\d+\s*(?:mg|mcg|ml|g)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(1).strip()
                return name, 0.85

        lines = [l.strip() for l in text.splitlines() if l.strip()]
        for line in lines[:5]:
            if re.match(r"^[A-Z][a-z]+", line) and len(line) < 50:
                return line, 0.5

        return text.splitlines()[0].strip()[:50] if text.strip() else None, 0.3

    def _llm_fallback(self, ocr_text: str) -> dict[str, Any]:
        """Use the LLM to identify a drug name from noisy OCR text."""
        if self._llm is None:
            return {"drug_name": None, "confidence": 0.0}

        import asyncio

        prompt = (
            "The following text was extracted via OCR from a medication package label in Hong Kong. "
            "Identify the drug name (generic name in English). Reply with ONLY the drug name, nothing else.\n\n"
            f"OCR text:\n{ocr_text[:500]}"
        )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(asyncio.run, self._llm.generate(prompt, max_tokens=50, temperature=0.1)).result()
            else:
                result = asyncio.run(self._llm.generate(prompt, max_tokens=50, temperature=0.1))

            drug_name = result.strip().split("\n")[0].strip()
            if drug_name and len(drug_name) < 60:
                return {"drug_name": drug_name, "confidence": 0.75}
        except Exception:
            logger.exception("LLM fallback failed")

        return {"drug_name": None, "confidence": 0.0}

    @staticmethod
    def _mock_extraction(path: Path) -> dict[str, Any]:
        """Fallback when PIL/Tesseract are not installed."""
        logger.warning("PIL/Tesseract not available — returning mock OCR result for %s", path.name)
        return {
            "extracted_text": f"[mock OCR] {path.name}",
            "drug_name": None,
            "confidence": 0.0,
        }
