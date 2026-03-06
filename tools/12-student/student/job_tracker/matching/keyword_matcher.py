"""Keyword matching: exact + fuzzy + semantic similarity scoring."""

from __future__ import annotations

import logging

from rapidfuzz import fuzz

logger = logging.getLogger("openclaw.student.job_tracker.keyword_matcher")


def match_keywords(cv_skills: list[str], jd_skills: list[str]) -> dict:
    if not jd_skills:
        return {"match_score": 1.0, "matched_skills": [], "unmatched_jd_skills": []}
    if not cv_skills:
        return {"match_score": 0.0, "matched_skills": [], "unmatched_jd_skills": jd_skills}

    cv_lower = [s.lower().strip() for s in cv_skills]
    jd_lower = [s.lower().strip() for s in jd_skills]

    matched: list[str] = []
    unmatched: list[str] = []

    for jd_skill in jd_lower:
        found = False
        for cv_skill in cv_lower:
            if cv_skill == jd_skill:
                matched.append(jd_skill)
                found = True
                break
            if fuzz.ratio(cv_skill, jd_skill) >= 80:
                matched.append(jd_skill)
                found = True
                break
        if not found:
            unmatched.append(jd_skill)

    semantic_bonus = _semantic_boost(cv_lower, unmatched)
    newly_matched = [s for s in unmatched if s in semantic_bonus]
    matched.extend(newly_matched)
    unmatched = [s for s in unmatched if s not in semantic_bonus]

    score = len(matched) / len(jd_lower) if jd_lower else 0.0

    return {
        "match_score": round(score, 3),
        "matched_skills": sorted(set(matched)),
        "unmatched_jd_skills": sorted(set(unmatched)),
    }


def _semantic_boost(cv_skills: list[str], unmatched: list[str]) -> set[str]:
    """Attempt semantic similarity matching for remaining unmatched skills."""
    if not unmatched:
        return set()

    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        cv_embeddings = model.encode(cv_skills, convert_to_tensor=True)
        jd_embeddings = model.encode(unmatched, convert_to_tensor=True)
        cosine_scores = util.cos_sim(jd_embeddings, cv_embeddings)

        boosted = set()
        for i, jd_skill in enumerate(unmatched):
            max_sim = cosine_scores[i].max().item()
            if max_sim >= 0.6:
                boosted.add(jd_skill)
        return boosted
    except Exception:
        logger.debug("sentence-transformers unavailable, skipping semantic matching")
        return set()
