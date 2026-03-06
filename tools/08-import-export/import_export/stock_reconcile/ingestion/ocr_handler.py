"""OCR handler for scanned shipping documents."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path


class OCRHandler:
    """Extracts text from scanned document images using configurable OCR engine."""

    SUPPORTED_ENGINES = ("tesseract", "vision")

    def __init__(self, engine: str = "tesseract") -> None:
        if engine not in self.SUPPORTED_ENGINES:
            raise ValueError(f"Unsupported OCR engine: {engine}. Use one of {self.SUPPORTED_ENGINES}")
        self.engine = engine

    def process(self, image_path: str) -> str:
        preprocessed = self.preprocess_image(image_path)
        target = preprocessed or image_path

        if self.engine == "tesseract":
            return self._tesseract_ocr(target)
        elif self.engine == "vision":
            return self._vision_ocr(target)
        return ""

    def preprocess_image(self, image_path: str) -> str | None:
        """Enhance image for better OCR: grayscale, contrast, sharpen, binarize."""
        try:
            from PIL import Image, ImageEnhance, ImageFilter
        except ImportError:
            return None

        img = Image.open(image_path)

        if img.mode != "L":
            img = img.convert("L")

        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.8)

        img = img.filter(ImageFilter.SHARPEN)

        img = img.point(lambda x: 0 if x < 140 else 255, "1")

        suffix = Path(image_path).suffix or ".png"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        img.save(tmp.name)
        return tmp.name

    def _tesseract_ocr(self, image_path: str) -> str:
        try:
            result = subprocess.run(
                ["tesseract", image_path, "stdout", "-l", "eng+chi_tra", "--psm", "6"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.stdout.strip()
        except FileNotFoundError:
            raise RuntimeError("tesseract is not installed or not in PATH")
        except subprocess.TimeoutExpired:
            raise RuntimeError("OCR processing timed out")

    def _vision_ocr(self, image_path: str) -> str:
        """Placeholder for cloud Vision API (Google / Azure)."""
        raise NotImplementedError(
            "Cloud Vision OCR is not yet configured. "
            "Set VISION_API_KEY in config to enable."
        )
