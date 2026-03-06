"""FAQ matching engine for the ClientPortal Bot."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("openclaw.immigration.bot.faq")

DEFAULT_KB_PATH = Path(__file__).resolve().parent / "knowledge_base.yaml"

FAQ_PROMPT = """\
You are a knowledgeable Hong Kong immigration assistant. Answer the user's question \
based ONLY on the following FAQ knowledge base. If the answer is not covered, say so.

Language: {lang_label}
Respond in {lang_label}.

Knowledge base:
{kb_text}

User question: {question}

Answer concisely and helpfully:"""


def load_knowledge_base(path: str | Path | None = None) -> list[dict]:
    """Load FAQ entries from a YAML file.

    Each entry is a dict with keys: question, question_zh, answer, answer_zh, keywords.
    """
    import yaml

    target = Path(path) if path else DEFAULT_KB_PATH
    if not target.exists():
        logger.warning("FAQ knowledge base not found at %s", target)
        return []

    with open(target, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    return data.get("faqs", []) if isinstance(data, dict) else data


async def answer_faq(
    question: str,
    llm: Any,
    knowledge_base: list[dict],
    lang: str = "en",
) -> str | None:
    """Try to answer the user's question from the FAQ knowledge base.

    First attempts keyword matching; falls back to LLM with FAQ context.
    Returns None if no confident answer can be produced.
    """
    keyword_match = _keyword_match(question, knowledge_base, lang)
    if keyword_match:
        return keyword_match

    return await _llm_answer(question, llm, knowledge_base, lang)


def _keyword_match(
    question: str,
    knowledge_base: list[dict],
    lang: str,
) -> str | None:
    """Simple keyword-overlap matching against the FAQ entries."""
    question_lower = question.lower()
    tokens = set(question_lower.split())

    best_score = 0
    best_answer: str | None = None

    for entry in knowledge_base:
        keywords = {k.lower() for k in entry.get("keywords", [])}
        q_text = entry.get("question", "").lower()
        q_text_zh = entry.get("question_zh", "")

        keyword_overlap = len(tokens & keywords)
        q_overlap = sum(1 for t in tokens if t in q_text)
        score = keyword_overlap * 2 + q_overlap

        if any(char in question for char in q_text_zh) and q_text_zh:
            score += 3

        if score > best_score and score >= 3:
            best_score = score
            answer_key = "answer_zh" if lang == "zh" else "answer"
            best_answer = entry.get(answer_key) or entry.get("answer", "")

    return best_answer


async def _llm_answer(
    question: str,
    llm: Any,
    knowledge_base: list[dict],
    lang: str,
) -> str | None:
    """Use the LLM to answer the question with FAQ context."""
    if not knowledge_base:
        return None

    lang_label = "Traditional Chinese (繁體中文)" if lang == "zh" else "English"
    kb_text = _format_kb_for_prompt(knowledge_base, lang)

    prompt = FAQ_PROMPT.format(
        lang_label=lang_label,
        kb_text=kb_text,
        question=question,
    )

    try:
        result = await llm.complete(prompt, max_tokens=500, temperature=0.3)
        answer = result.strip()
        if answer and "not covered" not in answer.lower() and len(answer) > 10:
            return answer
    except Exception:
        logger.exception("LLM FAQ answer failed")

    return None


def _format_kb_for_prompt(knowledge_base: list[dict], lang: str) -> str:
    lines: list[str] = []
    for i, entry in enumerate(knowledge_base, 1):
        q_key = "question_zh" if lang == "zh" else "question"
        a_key = "answer_zh" if lang == "zh" else "answer"
        q = entry.get(q_key) or entry.get("question", "")
        a = entry.get(a_key) or entry.get("answer", "")
        lines.append(f"Q{i}: {q}\nA{i}: {a}\n")
    return "\n".join(lines)
