"""Caption and hashtag optimisation for HK solopreneur social posts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openclaw_shared.database import get_db

logger = logging.getLogger(__name__)

PLATFORM_CAPTION_LIMITS: dict[str, int] = {
    "instagram_feed": 2200,
    "instagram_story": 200,
    "instagram_reel": 2200,
    "facebook_page": 63206,
    "facebook_story": 200,
    "whatsapp_status": 700,
}

HK_POPULAR_HASHTAGS: list[str] = [
    "hkig", "hongkong", "hklife", "852", "hkfoodie",
    "hkshop", "hkbeauty", "hkgirl", "hkcafe", "hkfood",
    "discoverhongkong", "instahk", "hongkonglife", "hkstyle",
    "explorehk", "hkshopping", "hkblogger", "hklocalshop",
]

_OPTIMIZE_PROMPT = (
    "You are a social media copywriting expert for Hong Kong small businesses. "
    "Rewrite the following post caption optimised for {platform}. "
    "Keep it engaging, concise (under {limit} characters), and culturally "
    "relevant for an HK audience. Language: {language}.\n\n"
    "Original caption:\n{text}\n\n"
    "Return ONLY the optimised caption text."
)


async def optimize_caption(
    text: str,
    platform: str,
    llm: Any = None,
    language: str = "en",
) -> str:
    """Optimise *text* for the given *platform* via LLM, or trim manually.

    If no LLM is available, performs basic length-truncation only.
    """
    limit = PLATFORM_CAPTION_LIMITS.get(platform, 2200)

    if llm is not None:
        try:
            prompt = _OPTIMIZE_PROMPT.format(
                platform=platform, limit=limit, language=language, text=text,
            )
            result = await llm.generate(prompt)
            optimised = result if isinstance(result, str) else str(result)
            return optimised[:limit]
        except Exception as exc:
            logger.warning("LLM caption optimisation failed: %s", exc)

    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def suggest_hashtags(
    text: str,
    category: str | None = None,
    db_path: str | Path | None = None,
    limit: int = 15,
) -> list[str]:
    """Suggest hashtags based on content text, optional category, and library.

    Combines library lookups (sorted by avg_engagement) with HK-popular
    defaults to reach *limit* suggestions.
    """
    tags: list[str] = []

    if db_path:
        try:
            with get_db(db_path) as conn:
                query = "SELECT hashtag FROM hashtag_library"
                params: list[Any] = []
                if category:
                    query += " WHERE category = ?"
                    params.append(category)
                query += " ORDER BY avg_engagement DESC LIMIT ?"
                params.append(limit)
                rows = conn.execute(query, params).fetchall()
                tags.extend(row["hashtag"] for row in rows)
        except Exception as exc:
            logger.debug("Hashtag library lookup failed: %s", exc)

    text_lower = text.lower()
    category_tags: dict[str, list[str]] = {
        "food": ["hkfoodie", "hkfood", "hkcafe", "hkeats", "foodiehk"],
        "beauty": ["hkbeauty", "hkskincare", "beautyhk", "hkmakeup"],
        "fashion": ["hkfashion", "hkstyle", "hkshopping", "ootdhk"],
        "fitness": ["hkfitness", "hkgym", "fitnesshk", "healthyhk"],
        "retail": ["hkshop", "hklocalshop", "hkshopping", "shophk"],
    }

    if category and category in category_tags:
        tags.extend(category_tags[category])
    else:
        for cat_key, cat_tags in category_tags.items():
            if cat_key in text_lower:
                tags.extend(cat_tags[:3])

    seen: set[str] = set()
    unique: list[str] = []
    for tag in tags:
        normalised = tag.lstrip("#").lower()
        if normalised not in seen:
            seen.add(normalised)
            unique.append(normalised)

    remaining = limit - len(unique)
    if remaining > 0:
        for ht in HK_POPULAR_HASHTAGS:
            if ht not in seen:
                unique.append(ht)
                seen.add(ht)
                if len(unique) >= limit:
                    break

    return [f"#{t}" for t in unique[:limit]]
