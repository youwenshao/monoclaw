"""Image preprocessing pipeline for OCR input quality improvement."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

logger = logging.getLogger("openclaw.immigration.ocr.preprocessor")


def _deskew_pil(image: "Image.Image") -> "Image.Image":
    """Attempt to deskew a PIL image using simple heuristics."""
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
        rotated = cv2.warpAffine(arr, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        from PIL import Image as PILImage
        return PILImage.fromarray(rotated)
    except ImportError:
        return image


def _adaptive_threshold(image: "Image.Image") -> "Image.Image":
    """Apply adaptive thresholding for cleaner text extraction."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        result = cv2.adaptiveThreshold(arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 15, 8)
        from PIL import Image as PILImage
        return PILImage.fromarray(result)
    except ImportError:
        return image.convert("L")


def _border_crop(image: "Image.Image", margin_pct: float = 0.02) -> "Image.Image":
    """Crop dark borders from scanned documents."""
    w, h = image.size
    mx = int(w * margin_pct)
    my = int(h * margin_pct)
    return image.crop((mx, my, w - mx, h - my))


def _perspective_correction_hkid(image: "Image.Image") -> "Image.Image":
    """Perspective correction tuned for HKID card dimensions (85.6 x 54mm)."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        blurred = cv2.GaussianBlur(arr, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        if not contours:
            return image

        largest = max(contours, key=cv2.contourArea)
        peri = cv2.arcLength(largest, True)
        approx = cv2.approxPolyDP(largest, 0.02 * peri, True)

        if len(approx) != 4:
            return image

        pts = approx.reshape(4, 2).astype(np.float32)
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]
        d = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(d)]
        rect[3] = pts[np.argmax(d)]

        target_w, target_h = 856, 540
        dst = np.array([[0, 0], [target_w, 0], [target_w, target_h], [0, target_h]], dtype=np.float32)
        matrix = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(np.array(image), matrix, (target_w, target_h))
        from PIL import Image as PILImage
        return PILImage.fromarray(warped)
    except ImportError:
        return image
    except Exception as exc:
        logger.debug("Perspective correction skipped: %s", exc)
        return image


def _detect_row_lines(image: "Image.Image") -> "Image.Image":
    """Detect and remove horizontal ruling lines common in bank statements."""
    try:
        import cv2
        import numpy as np

        arr = np.array(image.convert("L"))
        _, binary = cv2.threshold(arr, 180, 255, cv2.THRESH_BINARY_INV)
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (arr.shape[1] // 4, 1))
        detected_lines = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)
        repair_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 3))
        cleaned = cv2.subtract(binary, detected_lines)
        cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, repair_kernel)
        result = cv2.bitwise_not(cleaned)
        from PIL import Image as PILImage
        return PILImage.fromarray(result)
    except ImportError:
        return image


def preprocess_image(file_path: str, doc_type: str) -> str:
    """Preprocess a document image and return the path to the result.

    Processing steps applied by doc_type:
    - All types: deskew, adaptive threshold, border crop
    - hkid: perspective correction
    - bank_statement: row-line removal

    Returns the original path if any processing step fails entirely.
    """
    try:
        from PIL import Image
    except ImportError:
        logger.info("Pillow not installed — skipping preprocessing")
        return file_path

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
        image = _border_crop(image)
        image = _deskew_pil(image)

        if doc_type == "hkid":
            image = _perspective_correction_hkid(image)
        elif doc_type == "bank_statement":
            image = _detect_row_lines(image)

        image = _adaptive_threshold(image)

        suffix = path.suffix or ".png"
        out = tempfile.NamedTemporaryFile(suffix=suffix, prefix="ocr_prep_", delete=False)
        image.save(out.name)
        logger.debug("Preprocessed image saved to %s", out.name)
        return out.name

    except Exception as exc:
        logger.warning("Preprocessing failed for %s: %s — returning original", file_path, exc)
        return file_path
