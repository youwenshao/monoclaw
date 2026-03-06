"""Table and line-item detection for structured invoice data extraction."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.accounting.ocr.line_extractor")


def detect_table_structure(image_path: str) -> dict[str, Any]:
    """Detect table regions in an invoice image using Hough line transforms.

    Returns a dict with:
        has_table: bool
        horizontal_lines: list of y-coordinates
        vertical_lines: list of x-coordinates
        table_bbox: bounding box of the detected table region or None
        row_boundaries: list of (y_start, y_end) tuples for each row
    """
    result: dict[str, Any] = {
        "has_table": False,
        "horizontal_lines": [],
        "vertical_lines": [],
        "table_bbox": None,
        "row_boundaries": [],
    }

    try:
        import cv2
        import numpy as np

        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            logger.warning("Cannot read image: %s", image_path)
            return result

        h, w = img.shape
        _, binary = cv2.threshold(img, 180, 255, cv2.THRESH_BINARY_INV)

        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (w // 6, 1))
        horizontal_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, horizontal_kernel, iterations=2)

        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 6))
        vertical_mask = cv2.morphologyEx(binary, cv2.MORPH_OPEN, vertical_kernel, iterations=2)

        h_contours, _ = cv2.findContours(horizontal_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        v_contours, _ = cv2.findContours(vertical_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        h_lines = sorted({int(cv2.boundingRect(c)[1]) for c in h_contours})
        v_lines = sorted({int(cv2.boundingRect(c)[0]) for c in v_contours})

        result["horizontal_lines"] = h_lines
        result["vertical_lines"] = v_lines

        if len(h_lines) >= 2 and len(v_lines) >= 2:
            result["has_table"] = True
            result["table_bbox"] = {
                "x": v_lines[0],
                "y": h_lines[0],
                "width": v_lines[-1] - v_lines[0],
                "height": h_lines[-1] - h_lines[0],
            }

            row_bounds = []
            for i in range(len(h_lines) - 1):
                row_bounds.append((h_lines[i], h_lines[i + 1]))
            result["row_boundaries"] = row_bounds

        return result

    except ImportError:
        logger.warning("OpenCV not available for table detection")
        return result
    except Exception as exc:
        logger.warning("Table detection failed: %s", exc)
        return result


def extract_line_items(
    ocr_blocks: list[dict[str, Any]],
    table_structure: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Group OCR text blocks into table rows representing invoice line items.

    If table_structure is provided, uses row boundaries to group blocks.
    Otherwise, groups blocks by vertical proximity (y-coordinate clustering).

    Returns a list of dicts with: description, quantity, unit_price, amount.
    """
    if not ocr_blocks:
        return []

    if table_structure and table_structure.get("row_boundaries"):
        return _extract_with_structure(ocr_blocks, table_structure)

    return _extract_by_proximity(ocr_blocks)


def _extract_with_structure(
    ocr_blocks: list[dict[str, Any]],
    table_structure: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract line items using detected table row boundaries."""
    rows: list[list[dict[str, Any]]] = [[] for _ in table_structure["row_boundaries"]]

    for block in ocr_blocks:
        bbox = block.get("bbox", {})
        block_y = bbox.get("y", 0)

        for i, (y_start, y_end) in enumerate(table_structure["row_boundaries"]):
            norm_start = y_start / 1000.0 if y_start > 1 else y_start
            norm_end = y_end / 1000.0 if y_end > 1 else y_end
            if norm_start <= block_y <= norm_end:
                rows[i].append(block)
                break

    return _rows_to_line_items(rows)


def _extract_by_proximity(
    ocr_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group OCR blocks into rows by y-coordinate proximity."""
    if not ocr_blocks:
        return []

    sorted_blocks = sorted(ocr_blocks, key=lambda b: -b.get("bbox", {}).get("y", 0))

    rows: list[list[dict[str, Any]]] = []
    current_row: list[dict[str, Any]] = []
    last_y: float | None = None
    threshold = 0.02

    for block in sorted_blocks:
        block_y = block.get("bbox", {}).get("y", 0)
        if last_y is None or abs(block_y - last_y) <= threshold:
            current_row.append(block)
        else:
            if current_row:
                rows.append(current_row)
            current_row = [block]
        last_y = block_y

    if current_row:
        rows.append(current_row)

    return _rows_to_line_items(rows)


def _rows_to_line_items(rows: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Convert grouped row blocks into structured line item dicts."""
    import re

    amount_pattern = re.compile(r"[\d,]+\.?\d*")
    line_items: list[dict[str, Any]] = []

    for row in rows:
        if not row:
            continue

        sorted_cols = sorted(row, key=lambda b: b.get("bbox", {}).get("x", 0))
        texts = [b.get("text", "").strip() for b in sorted_cols]
        full_text = " ".join(texts)

        numbers = amount_pattern.findall(full_text)
        numbers_clean = [n.replace(",", "") for n in numbers if "." in n or len(n.replace(",", "")) > 0]
        float_numbers = []
        for n in numbers_clean:
            try:
                float_numbers.append(float(n))
            except ValueError:
                continue

        if not float_numbers:
            continue

        item: dict[str, Any] = {"description": "", "quantity": None, "unit_price": None, "amount": 0.0}

        desc_parts = []
        for t in texts:
            cleaned = amount_pattern.sub("", t).strip(" .-$")
            if cleaned and not cleaned.replace(",", "").replace(".", "").isdigit():
                desc_parts.append(cleaned)
        item["description"] = " ".join(desc_parts).strip()

        if not item["description"]:
            continue

        if len(float_numbers) >= 3:
            item["quantity"] = float_numbers[-3]
            item["unit_price"] = float_numbers[-2]
            item["amount"] = float_numbers[-1]
        elif len(float_numbers) == 2:
            item["quantity"] = float_numbers[-2]
            item["amount"] = float_numbers[-1]
        elif len(float_numbers) == 1:
            item["amount"] = float_numbers[-1]

        line_items.append(item)

    return line_items
