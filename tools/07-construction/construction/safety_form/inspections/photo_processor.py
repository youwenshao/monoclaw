"""Inspection photo processing — storage, EXIF extraction, metadata."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.construction.safety_form.inspections.photo")


async def save_inspection_photo(
    workspace: Path,
    inspection_id: int,
    item_id: int,
    photo: Any,
) -> str:
    """Save an uploaded inspection photo and return the relative path.

    Parameters:
        workspace: Root workspace directory
        inspection_id: ID of the parent daily_inspections record
        item_id: ID of the checklist_items record
        photo: FastAPI UploadFile instance
    """
    dest_dir = Path(workspace) / "photos" / "inspections" / str(inspection_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = _get_extension(photo.filename or "photo.jpg")
    filename = f"item_{item_id}_{datetime.now().strftime('%H%M%S')}{ext}"
    dest_path = dest_dir / filename

    contents = await photo.read()
    dest_path.write_bytes(contents)

    relative = str(dest_path.relative_to(workspace))
    logger.info("Photo saved: %s (%d bytes)", relative, len(contents))
    return relative


def extract_exif_data(file_path: str) -> dict:
    """Extract GPS coordinates and timestamp from EXIF metadata.

    Returns a dict with 'latitude', 'longitude', 'timestamp' keys.
    Missing values are None.
    """
    result: dict[str, Any] = {
        "latitude": None,
        "longitude": None,
        "timestamp": None,
    }

    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        img = Image.open(file_path)
        exif_data = img._getexif()  # type: ignore[attr-defined]
        if not exif_data:
            logger.debug("No EXIF data in %s", file_path)
            return result

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, tag_id)
            if tag_name == "DateTimeOriginal":
                try:
                    result["timestamp"] = datetime.strptime(
                        str(value), "%Y:%m:%d %H:%M:%S"
                    ).isoformat()
                except (ValueError, TypeError):
                    pass
            elif tag_name == "GPSInfo":
                gps = _parse_gps_info(value, GPSTAGS)
                result["latitude"] = gps.get("latitude")
                result["longitude"] = gps.get("longitude")

    except ImportError:
        logger.debug("Pillow not installed — EXIF extraction unavailable")
    except Exception:
        logger.exception("EXIF extraction failed for %s", file_path)

    return result


def get_photo_metadata(file_path: str) -> dict:
    """Get photo metadata with EXIF fallback.

    If EXIF data is unavailable, returns file-system derived metadata.
    """
    exif = extract_exif_data(file_path)

    path = Path(file_path)
    stat = path.stat() if path.exists() else None

    return {
        "filename": path.name,
        "file_size": stat.st_size if stat else 0,
        "latitude": exif["latitude"],
        "longitude": exif["longitude"],
        "timestamp": exif["timestamp"] or (
            datetime.fromtimestamp(stat.st_mtime).isoformat() if stat else None
        ),
        "has_exif": exif["timestamp"] is not None or exif["latitude"] is not None,
    }


def _get_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in (".jpg", ".jpeg", ".png", ".heic", ".webp") else ".jpg"


def _parse_gps_info(gps_info: dict, gpstags: dict) -> dict:
    """Parse GPS EXIF tags into decimal latitude/longitude."""
    parsed: dict[str, Any] = {}
    for key, val in gps_info.items():
        tag_name = gpstags.get(key, key)
        parsed[tag_name] = val

    lat = _dms_to_decimal(
        parsed.get("GPSLatitude"), parsed.get("GPSLatitudeRef", "N")
    )
    lng = _dms_to_decimal(
        parsed.get("GPSLongitude"), parsed.get("GPSLongitudeRef", "E")
    )
    return {"latitude": lat, "longitude": lng}


def _dms_to_decimal(dms: Any, ref: str) -> float | None:
    """Convert EXIF DMS (degrees, minutes, seconds) to decimal degrees."""
    if not dms or len(dms) < 3:
        return None
    try:
        d = float(dms[0])
        m = float(dms[1])
        s = float(dms[2])
        decimal = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
