"""AI-powered defect classification with keyword fallback."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("openclaw.construction.defects_manager.defects.categorizer")


def get_category_keywords() -> dict[str, list[str]]:
    """Return keyword lists for each defect category."""
    return {
        "water_seepage": [
            "water", "leak", "leaking", "seepage", "damp", "dampness", "mould",
            "mold", "moisture", "drip", "dripping", "wet", "stain", "watermark",
            "滲水", "漏水", "潮濕", "發霉",
        ],
        "concrete_spalling": [
            "spalling", "concrete", "flaking", "chipping", "rebar", "exposed",
            "peeling", "crumbling", "render", "plaster",
            "石屎剝落", "批盪", "鋼筋外露",
        ],
        "plumbing": [
            "pipe", "drain", "drainage", "blocked", "blockage", "toilet",
            "tap", "faucet", "sewage", "sewer", "sink", "basin",
            "水管", "喉管", "淤塞", "排水",
        ],
        "electrical": [
            "electrical", "wiring", "wire", "socket", "switch", "power",
            "outage", "short circuit", "fuse", "breaker", "light", "lighting",
            "電線", "插座", "開關", "跳掣",
        ],
        "lift": [
            "lift", "elevator", "escalator", "door", "button", "noise",
            "stuck", "malfunction",
            "升降機", "電梯",
        ],
        "window": [
            "window", "glass", "broken glass", "frame", "seal", "hinge",
            "aluminium", "sliding", "shattered",
            "窗", "玻璃", "窗鉸",
        ],
        "common_area": [
            "lobby", "corridor", "staircase", "stairwell", "parking",
            "playground", "garden", "clubhouse", "roof", "podium",
            "大堂", "走廊", "樓梯", "公共地方",
        ],
        "structural": [
            "crack", "cracking", "structural", "beam", "column", "wall crack",
            "foundation", "settlement", "tilting", "slab",
            "裂縫", "結構", "柱", "樑", "沉降",
        ],
    }


def _keyword_classify(description: str) -> str:
    """Classify by keyword matching; returns 'other' if no match."""
    text = description.lower()
    keywords = get_category_keywords()
    scores: dict[str, int] = {}
    for category, words in keywords.items():
        score = sum(1 for w in words if w.lower() in text)
        if score > 0:
            scores[category] = score
    if scores:
        return max(scores, key=scores.get)  # type: ignore[arg-type]
    return "other"


async def categorize_defect(
    llm: Any | None,
    description: str,
    photo_path: str | None = None,
) -> str:
    """Categorise a defect using LLM when available, else keyword fallback.

    *llm* should be an :class:`openclaw_shared.llm.LLMProvider` instance or
    ``None`` (triggers keyword fallback).
    """
    if llm is not None:
        try:
            from construction.defects_manager.models.llm_handler import DefectLLM

            handler = DefectLLM(llm)
            category = await handler.classify(description)
            if category != "other":
                logger.info("LLM classified defect as %s", category)
                return category
        except Exception:
            logger.exception("LLM categorisation failed — using keyword fallback")

    category = _keyword_classify(description)
    logger.info("Keyword classified defect as %s", category)
    return category
