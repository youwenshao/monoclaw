"""Image optimisation per social-media platform using Pillow."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)

PLATFORM_SIZES: dict[str, tuple[int, int]] = {
    "instagram_feed": (1080, 1080),
    "instagram_story": (1080, 1920),
    "instagram_reel": (1080, 1920),
    "facebook_page": (1200, 630),
    "facebook_story": (1080, 1920),
    "whatsapp_status": (1080, 1920),
}


def optimize_for_platform(image_path: str | Path, platform: str) -> Path:
    """Resize and crop *image_path* for *platform*, saving a new file.

    Uses ``ImageOps.fit`` for centre-crop resizing. The optimised copy is
    saved alongside the original with a ``_<platform>`` suffix.

    Returns:
        Path to the newly created optimised image.

    Raises:
        ValueError: If *platform* is not recognised.
    """
    image_path = Path(image_path)
    size = PLATFORM_SIZES.get(platform)
    if size is None:
        raise ValueError(
            f"Unknown platform '{platform}'. "
            f"Supported: {', '.join(PLATFORM_SIZES)}"
        )

    with Image.open(image_path) as img:
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        optimised = ImageOps.fit(img, size, method=Image.LANCZOS)

        out_name = f"{image_path.stem}_{platform}{image_path.suffix}"
        out_path = image_path.parent / out_name
        optimised.save(out_path, quality=90, optimize=True)

    logger.info("Optimised %s → %s (%dx%d)", image_path.name, out_path.name, *size)
    return out_path


def optimize_for_all_platforms(
    image_path: str | Path,
    platforms: list[str] | None = None,
) -> dict[str, Path]:
    """Create optimised copies for every requested platform.

    Args:
        image_path: Source image.
        platforms: List of platform keys. Defaults to all known platforms.

    Returns:
        Mapping of platform name to optimised file path.
    """
    targets = platforms or list(PLATFORM_SIZES)
    results: dict[str, Path] = {}
    for platform in targets:
        try:
            results[platform] = optimize_for_platform(image_path, platform)
        except Exception as exc:
            logger.warning("Optimisation failed for %s: %s", platform, exc)
    return results
