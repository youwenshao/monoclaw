"""Video format validation and basic metadata extraction.

Actual transcoding via moviepy/ffmpeg is optional and gated behind an
import check so the module works even when those heavy deps are absent.
"""

from __future__ import annotations

import logging
import subprocess
import json as _json
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PLATFORM_VIDEO_LIMITS: dict[str, dict[str, Any]] = {
    "instagram_reel": {"max_duration_s": 90, "max_size_mb": 100, "aspect": "9:16"},
    "instagram_story": {"max_duration_s": 60, "max_size_mb": 100, "aspect": "9:16"},
    "facebook_page": {"max_duration_s": 240 * 60, "max_size_mb": 4096, "aspect": "any"},
    "whatsapp_status": {"max_duration_s": 30, "max_size_mb": 16, "aspect": "any"},
}


def get_video_info(video_path: str | Path) -> dict[str, Any]:
    """Return basic metadata: duration (seconds), resolution, and file size.

    Tries ``ffprobe`` first; falls back to file-size-only if unavailable.
    """
    video_path = Path(video_path)
    info: dict[str, Any] = {
        "path": str(video_path),
        "size_mb": round(video_path.stat().st_size / (1024 * 1024), 2),
    }

    try:
        probe = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-print_format", "json",
                "-show_streams", "-show_format",
                str(video_path),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if probe.returncode == 0:
            data = _json.loads(probe.stdout)
            fmt = data.get("format", {})
            info["duration"] = float(fmt.get("duration", 0))

            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video":
                    info["width"] = stream.get("width")
                    info["height"] = stream.get("height")
                    info["codec"] = stream.get("codec_name")
                    break
    except FileNotFoundError:
        logger.debug("ffprobe not found — returning size-only info")
    except Exception as exc:
        logger.warning("ffprobe failed: %s", exc)

    return info


def validate_for_platform(video_path: str | Path, platform: str) -> dict[str, Any]:
    """Check whether a video meets a platform's constraints.

    Returns a dict with ``valid`` (bool) and a list of ``issues``.
    """
    limits = PLATFORM_VIDEO_LIMITS.get(platform, {})
    info = get_video_info(video_path)
    issues: list[str] = []

    max_dur = limits.get("max_duration_s")
    if max_dur and info.get("duration", 0) > max_dur:
        issues.append(
            f"Duration {info['duration']:.0f}s exceeds {platform} limit of {max_dur}s"
        )

    max_size = limits.get("max_size_mb")
    if max_size and info.get("size_mb", 0) > max_size:
        issues.append(
            f"File size {info['size_mb']}MB exceeds {platform} limit of {max_size}MB"
        )

    return {"valid": len(issues) == 0, "issues": issues, "info": info}


def optimize_video(video_path: str | Path, platform: str) -> Path:
    """Optimise a video for *platform* (if moviepy is available).

    Falls back to returning the original path when transcoding deps
    are missing, after logging a warning.
    """
    video_path = Path(video_path)
    validation = validate_for_platform(video_path, platform)

    if validation["valid"]:
        return video_path

    try:
        from moviepy.editor import VideoFileClip  # type: ignore[import-untyped]
    except ImportError:
        logger.warning(
            "moviepy not installed — cannot auto-optimise video for %s. "
            "Issues: %s",
            platform,
            validation["issues"],
        )
        return video_path

    limits = PLATFORM_VIDEO_LIMITS.get(platform, {})
    out_path = video_path.parent / f"{video_path.stem}_{platform}.mp4"

    clip = VideoFileClip(str(video_path))
    max_dur = limits.get("max_duration_s")
    if max_dur and clip.duration > max_dur:
        clip = clip.subclip(0, max_dur)

    clip.write_videofile(
        str(out_path),
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        logger=None,
    )
    clip.close()

    logger.info("Optimised video → %s", out_path.name)
    return out_path
