"""Image processing pipeline for listing photos.

Processes images ONE at a time for memory safety on constrained devices.
Uses Pillow for resize, brightness/contrast normalisation, and EAA watermark overlay.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

from openclaw_shared.database import get_db

logger = logging.getLogger("listing_sync.processing.images")

PLATFORM_SPECS: dict[str, tuple[int, int]] = {
    "28hse": (1024, 768),
    "squarefoot": (1200, 900),
    "whatsapp": (1200, 900),
}


def _normalise_brightness(img: Image.Image) -> Image.Image:
    """Light brightness/contrast normalisation to correct underexposed property photos."""
    enhancer = ImageEnhance.Brightness(img)
    img = enhancer.enhance(1.05)
    enhancer = ImageEnhance.Contrast(img)
    return enhancer.enhance(1.08)


def _apply_eaa_watermark(
    img: Image.Image,
    eaa_license: str,
    opacity: float = 0.6,
    font_size: int = 14,
) -> Image.Image:
    """Overlay EAA licence number as a semi-transparent watermark in the bottom-right.

    HK Estate Agents Authority requires licence numbers to be visible
    on all marketing materials.
    """
    if not eaa_license:
        return img

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()

    text = f"EAA Lic: {eaa_license}"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    padding = 8
    x = img.width - text_w - padding - 10
    y = img.height - text_h - padding - 10

    draw.rectangle(
        [x - padding, y - padding, x + text_w + padding, y + text_h + padding],
        fill=(0, 0, 0, int(255 * opacity * 0.5)),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 255, 255, int(255 * opacity)),
    )

    if img.mode != "RGBA":
        img = img.convert("RGBA")
    return Image.alpha_composite(img, overlay)


def _resize_for_platform(img: Image.Image, spec: tuple[int, int]) -> Image.Image:
    """Resize maintaining aspect ratio, then pad to exact spec with white background."""
    target_w, target_h = spec
    img.thumbnail((target_w, target_h), Image.LANCZOS)

    if img.size == (target_w, target_h):
        return img

    canvas = Image.new("RGB", (target_w, target_h), (255, 255, 255))
    offset_x = (target_w - img.width) // 2
    offset_y = (target_h - img.height) // 2
    paste_img = img.convert("RGB") if img.mode != "RGB" else img
    canvas.paste(paste_img, (offset_x, offset_y))
    return canvas


def _process_single_image(
    original_path: Path,
    output_dir: Path,
    eaa_license: str,
    watermark_opacity: float,
    watermark_font_size: int,
) -> dict[str, str]:
    """Process one image: normalise, watermark, and resize for each platform."""
    results: dict[str, str] = {}

    with Image.open(original_path) as img:
        img = _normalise_brightness(img)
        watermarked = _apply_eaa_watermark(img, eaa_license, watermark_opacity, watermark_font_size)

        for platform, spec in PLATFORM_SPECS.items():
            resized = _resize_for_platform(watermarked, spec)
            out_name = f"{original_path.stem}_{platform}{original_path.suffix}"
            out_path = output_dir / out_name
            final = resized.convert("RGB") if resized.mode == "RGBA" else resized
            final.save(str(out_path), quality=85, optimize=True)
            results[platform] = str(out_path)
            logger.debug("Processed %s for %s -> %s", original_path.name, platform, out_path)

    return results


async def process_listing_images(
    db_path: str | Path,
    listing_id: int,
    workspace: str | Path,
    eaa_license: str = "",
    watermark_opacity: float = 0.6,
    watermark_font_size: int = 14,
) -> dict:
    """Process all images for a listing.

    Reads image records from DB, processes ONE at a time to keep memory low,
    then writes processed paths back to the database.
    """
    workspace = Path(workspace).expanduser()
    output_dir = workspace / "listing_images" / str(listing_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, original_path, sort_order FROM images WHERE listing_id = ? ORDER BY sort_order",
            (listing_id,),
        ).fetchall()

    if not rows:
        return {"listing_id": listing_id, "processed": 0, "error": "No images found"}

    processed_count = 0
    errors: list[str] = []

    for row in rows:
        image_id = row["id"]
        original = Path(row["original_path"])

        if not original.exists():
            errors.append(f"Missing: {original}")
            continue

        try:
            platform_paths = _process_single_image(
                original, output_dir, eaa_license, watermark_opacity, watermark_font_size,
            )
            with get_db(db_path) as conn:
                conn.execute(
                    "UPDATE images SET processed_paths = ?, watermarked = TRUE WHERE id = ?",
                    (json.dumps(platform_paths), image_id),
                )
            processed_count += 1
        except Exception:
            logger.exception("Failed to process image %s", original)
            errors.append(f"Error: {original.name}")

    return {
        "listing_id": listing_id,
        "processed": processed_count,
        "total": len(rows),
        "errors": errors or None,
    }
