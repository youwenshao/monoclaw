"""Manage heading styles per university formatting requirements."""

from __future__ import annotations

import json
from pathlib import Path

from docx import Document
from docx.shared import Pt


PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"


def set_heading_styles(doc: Document, profile: dict) -> None:
    heading_cfg = profile.get("heading_styles")
    if isinstance(heading_cfg, str):
        heading_cfg = json.loads(heading_cfg)
    if not heading_cfg:
        return

    for level_str, style_def in heading_cfg.items():
        style_name = f"Heading {level_str}"
        try:
            style = doc.styles[style_name]
        except KeyError:
            continue
        font = style.font
        if "font_size" in style_def:
            font.size = Pt(style_def["font_size"])
        if "bold" in style_def:
            font.bold = style_def["bold"]
        if "all_caps" in style_def:
            font.all_caps = style_def["all_caps"]


def get_style_config(university: str) -> dict:
    slug = university.lower().replace(" ", "_")
    profile_path = PROFILES_DIR / f"{slug}.json"
    if not profile_path.exists():
        profile_path = PROFILES_DIR / "generic.json"
    return json.loads(profile_path.read_text(encoding="utf-8"))
