"""Image preprocessing pipeline for invoice OCR quality improvement."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.accounting.ocr.preprocessor")


def deskew(image: "Image.Image") -> "Image.Image":
    """Correct skew in a scanned document image."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        coords = np.column_stack(np.where(arr < 128))
        if len(coords) < 50:
            return image

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle

        if abs(angle) < 0.5:
            return image

        h, w = arr.shape
        center = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            arr, matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        from PIL import Image as PILImage
        return PILImage.fromarray(rotated)
    except ImportError:
        return image


def enhance_contrast(image: "Image.Image") -> "Image.Image":
    """Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(arr)
        from PIL import Image as PILImage
        return PILImage.fromarray(enhanced)
    except ImportError:
        return image.convert("L")


def binarize(image: "Image.Image", adaptive: bool = True) -> "Image.Image":
    """Convert image to binary using adaptive or Otsu thresholding.

    Use adaptive=True for documents with uneven lighting (faded receipts).
    Use adaptive=False for clean scans where Otsu works well.
    """
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))

        if adaptive:
            result = cv2.adaptiveThreshold(
                arr, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY, 15, 8,
            )
        else:
            _, result = cv2.threshold(arr, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        from PIL import Image as PILImage
        return PILImage.fromarray(result)
    except ImportError:
        return image.convert("L")


def _remove_noise(image: "Image.Image") -> "Image.Image":
    """Remove salt-and-pepper noise with a median blur."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        denoised = cv2.medianBlur(arr, 3)
        from PIL import Image as PILImage
        return PILImage.fromarray(denoised)
    except ImportError:
        return image


def _border_crop(image: "Image.Image", margin_pct: float = 0.02) -> "Image.Image":
    """Crop dark borders from scanned documents."""
    w, h = image.size
    mx = int(w * margin_pct)
    my = int(h * margin_pct)
    return image.crop((mx, my, w - mx, h - my))


def preprocess_image(
    file_path: str,
    options: dict[str, Any] | None = None,
) -> str:
    """Preprocess an invoice image and return the path to the processed file.

    Options:
        deskew (bool): Correct skew. Default True.
        enhance_contrast (bool): Apply CLAHE. Default True.
        binarize (bool): Apply adaptive thresholding. Default False.
        denoise (bool): Remove noise. Default False.
        crop_borders (bool): Remove dark borders. Default True.

    Returns the original path if processing is not possible.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.info("Pillow not installed — skipping preprocessing")
        return file_path

    if options is None:
        options = {}

    path = Path(file_path)
    if not path.exists():
        logger.warning("File not found for preprocessing: %s", file_path)
        return file_path

    try:
        image = Image.open(path)
    except Exception as exc:
        logger.warning("Could not open image %s: %s", file_path, exc)
        return file_path

    try:
        if options.get("crop_borders", True):
            image = _border_crop(image)

        if options.get("deskew", True):
            image = deskew(image)

        if options.get("enhance_contrast", True):
            image = enhance_contrast(image)

        if options.get("denoise", False):
            image = _remove_noise(image)

        if options.get("binarize", False):
            image = binarize(image, adaptive=options.get("adaptive", True))

        suffix = path.suffix or ".png"
        out = tempfile.NamedTemporaryFile(suffix=suffix, prefix="inv_ocr_prep_", delete=False)
        image.save(out.name)
        logger.debug("Preprocessed invoice image saved to %s", out.name)
        return out.name

    except Exception as exc:
        logger.warning("Preprocessing failed for %s: %s — returning original", file_path, exc)
        return file_path
