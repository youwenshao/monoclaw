"""Language detection and Cantonese post-processing for bilingual transcription."""

from __future__ import annotations

import re


def detect_language(text: str) -> str:
    """Detect whether text is English, Chinese, or mixed.

    Returns 'en', 'zh', or 'mixed' based on character composition.
    CJK Unified Ideographs: U+4E00–U+9FFF
    CJK Extension A:        U+3400–U+4DBF
    CJK Compatibility:      U+F900–U+FAFF
    Bopomofo:               U+3100–U+312F
    """
    if not text or not text.strip():
        return "en"

    cjk_count = 0
    latin_count = 0

    for ch in text:
        cp = ord(ch)
        if (
            0x4E00 <= cp <= 0x9FFF
            or 0x3400 <= cp <= 0x4DBF
            or 0xF900 <= cp <= 0xFAFF
            or 0x3100 <= cp <= 0x312F
        ):
            cjk_count += 1
        elif (0x0041 <= cp <= 0x005A) or (0x0061 <= cp <= 0x007A):
            latin_count += 1

    total = cjk_count + latin_count
    if total == 0:
        return "en"

    cjk_ratio = cjk_count / total
    if cjk_ratio > 0.7:
        return "zh"
    if cjk_ratio < 0.3:
        return "en"
    return "mixed"


HK_MEDICAL_VOCABULARY: dict[str, str] = {
    "洗牙": "洗牙",
    "杜牙根": "杜牙根",
    "脫牙": "脫牙",
    "種牙": "種牙",
    "補牙": "補牙",
    "牙周病": "牙周病",
    "蛀牙": "蛀牙",
    "箍牙": "箍牙",
    "智慧齒": "智慧齒",
    "血壓高": "高血壓",
    "糖尿": "糖尿病",
    "膽固醇高": "高膽固醇",
    "傷風": "上呼吸道感染",
    "感冒": "上呼吸道感染",
    "肚痛": "腹痛",
    "頭痛": "頭痛",
    "頭暈": "頭暈",
    "嘔": "嘔吐",
    "痾": "腹瀉",
    "咳": "咳嗽",
    "喉嚨痛": "咽喉痛",
    "氣管炎": "支氣管炎",
    "肺炎": "肺炎",
    "哮喘": "哮喘",
    "濕疹": "濕疹",
    "荷爾蒙": "激素",
    "照X光": "X光檢查",
    "照超聲波": "超聲波檢查",
    "抽血": "抽血檢查",
    "驗血": "血液檢查",
    "磅數": "體重",
    "度高": "身高測量",
}


def post_process_cantonese(
    text: str,
    vocabulary: dict[str, str] | None = None,
) -> str:
    """Apply Cantonese medical vocabulary corrections to transcription text.

    Replaces colloquial HK Cantonese medical terms with standard forms
    using the built-in dictionary merged with any custom overrides.
    """
    vocab = dict(HK_MEDICAL_VOCABULARY)
    if vocabulary:
        vocab.update(vocabulary)

    result = text
    for colloquial, standard in sorted(vocab.items(), key=lambda x: -len(x[0])):
        result = re.sub(re.escape(colloquial), standard, result)

    return result
