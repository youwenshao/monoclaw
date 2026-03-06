"""Domain-specific prompt construction for academic translation."""

from __future__ import annotations

DOMAIN_INSTRUCTIONS: dict[str, str] = {
    "stem": (
        "You are translating a STEM (Science, Technology, Engineering, Mathematics) academic text. "
        "Preserve all mathematical notation, chemical formulae, variable names, and units exactly as written. "
        "Use standard technical terminology consistent with IEEE, ACM, and major STEM journals. "
        "Maintain the passive voice common in scientific writing when translating to English. "
        "For Chinese targets, prefer Hong Kong academic conventions (e.g. 資訊科技 not 信息技術, 軟件 not 軟體 for TC)."
    ),
    "social_science": (
        "You are translating a social science academic text (sociology, psychology, political science, economics, education). "
        "Preserve discipline-specific constructs (e.g. 'self-efficacy', 'social capital') using their established translations. "
        "Maintain nuanced hedging language ('suggests', 'indicates', 'appears to'). "
        "For Chinese targets, use terminology aligned with HK/Taiwan academic conventions."
    ),
    "humanities": (
        "You are translating a humanities text (literature, philosophy, history, cultural studies). "
        "Preserve literary style, rhetorical devices, and cultural references with appropriate annotations. "
        "Maintain the author's voice and register. When cultural concepts lack direct equivalents, "
        "transliterate and provide brief contextual glosses. Use Traditional Chinese conventions for TC targets."
    ),
    "medicine": (
        "You are translating a medical/biomedical academic text. "
        "Use standard medical terminology from MeSH and ICD classifications. "
        "Preserve drug names (use INN/generic names), dosages, anatomical terms, and statistical measures exactly. "
        "For Chinese targets, use the terminology standard of the Hong Kong Medical Association and "
        "Hong Kong College of Physicians (e.g. 糖尿病 for diabetes, 心臟病 for heart disease)."
    ),
    "law": (
        "You are translating a legal academic text. "
        "Use precise legal terminology consistent with the target jurisdiction. "
        "For English-Chinese legal translation, prefer Hong Kong bilingual legal terminology "
        "(e.g. 合約 for contract in HK context, 條例 for ordinance). "
        "Preserve Latin legal maxims and case citations in their original form. "
        "Maintain the formal register characteristic of legal writing."
    ),
    "business": (
        "You are translating a business/management academic text. "
        "Use standard business and finance terminology (e.g. ROI, EBITDA, market capitalisation). "
        "For Chinese targets, use Hong Kong financial terminology conventions "
        "(e.g. 股東 for shareholders, 營業額 for turnover/revenue). "
        "Preserve company names and brand names in their original language with established translations where available."
    ),
    "general": (
        "You are translating an academic text. "
        "Maintain formal academic register throughout. "
        "Preserve all proper nouns, citations, and technical terms accurately. "
        "When translating between English and Chinese, prefer Hong Kong Traditional Chinese conventions for TC targets."
    ),
}


def get_domain_system_prompt(domain: str, source_lang: str, target_lang: str) -> str:
    """Return a system prompt tuned for the academic domain.

    Args:
        domain: One of stem, social_science, humanities, medicine, law, business, general.
        source_lang: Source language code ('en', 'tc', 'sc').
        target_lang: Target language code ('en', 'tc', 'sc').

    Returns:
        A system prompt string for the LLM.
    """
    lang_names = {"en": "English", "tc": "Traditional Chinese", "sc": "Simplified Chinese"}
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)

    instructions = DOMAIN_INSTRUCTIONS.get(domain, DOMAIN_INSTRUCTIONS["general"])

    return (
        f"{instructions}\n\n"
        f"Translation direction: {src_name} → {tgt_name}.\n"
        f"Output ONLY the translated text. Do not include explanations, notes, or the original text.\n"
        f"Preserve paragraph structure, formatting markers, and any inline citations."
    )
