"""Parse pasted job description text into structured fields."""

from __future__ import annotations

import re


def parse_text(raw_text: str) -> dict:
    lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
    if not lines:
        return _empty()

    title = lines[0] if lines else ""
    company = ""
    location = "Hong Kong"
    salary_min: float | None = None
    salary_max: float | None = None
    requirements: list[str] = []
    skills: list[str] = []
    benefits: str | None = None

    in_requirements = False
    in_benefits = False
    benefit_lines: list[str] = []

    for line in lines[1:]:
        lower = line.lower()

        if re.match(r"^company\s*[:：]", lower):
            company = re.sub(r"^company\s*[:：]\s*", "", line, flags=re.IGNORECASE).strip()
            in_requirements = False
            in_benefits = False
            continue

        if re.match(r"^(location|地點)\s*[:：]", lower):
            location = re.sub(r"^(location|地點)\s*[:：]\s*", "", line, flags=re.IGNORECASE).strip()
            in_requirements = False
            in_benefits = False
            continue

        salary_match = re.search(r"(?:hk\$|hkd)\s*([\d,]+)\s*[-–to至]\s*(?:hk\$|hkd)?\s*([\d,]+)", lower)
        if salary_match:
            salary_min = float(salary_match.group(1).replace(",", ""))
            salary_max = float(salary_match.group(2).replace(",", ""))
            in_requirements = False
            in_benefits = False
            continue

        if re.match(r"^(requirements?|qualifications?|要求)\s*[:：]?", lower):
            in_requirements = True
            in_benefits = False
            rest = re.sub(r"^(requirements?|qualifications?|要求)\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip()
            if rest:
                requirements.append(rest)
            continue

        if re.match(r"^(benefits?|福利|what we offer)\s*[:：]?", lower):
            in_benefits = True
            in_requirements = False
            rest = re.sub(r"^(benefits?|福利|what we offer)\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip()
            if rest:
                benefit_lines.append(rest)
            continue

        if re.match(r"^(skills?|技能)\s*[:：]?", lower):
            in_requirements = False
            in_benefits = False
            rest = re.sub(r"^(skills?|技能)\s*[:：]?\s*", "", line, flags=re.IGNORECASE).strip()
            if rest:
                skills.extend(s.strip().lower() for s in re.split(r"[,，;；/]", rest) if s.strip())
            continue

        if in_requirements:
            cleaned = re.sub(r"^[-•·*]\s*", "", line).strip()
            if cleaned:
                requirements.append(cleaned)
        elif in_benefits:
            cleaned = re.sub(r"^[-•·*]\s*", "", line).strip()
            if cleaned:
                benefit_lines.append(cleaned)

    if benefit_lines:
        benefits = "; ".join(benefit_lines)

    return {
        "title": title,
        "company": company,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "location": location,
        "district": None,
        "job_type": "full_time",
        "industry": "",
        "requirements": requirements,
        "skills_required": skills,
        "benefits": benefits,
        "language": _detect_language(raw_text),
        "posted_date": None,
        "deadline": None,
    }


def _detect_language(text: str) -> str:
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    ascii_words = len(re.findall(r"[a-zA-Z]+", text))
    if chinese_chars > 20 and ascii_words > 20:
        return "bilingual"
    if chinese_chars > ascii_words:
        return "zh"
    return "en"


def _empty() -> dict:
    return {
        "title": "",
        "company": "",
        "salary_min": None,
        "salary_max": None,
        "location": "Hong Kong",
        "district": None,
        "job_type": "full_time",
        "industry": "",
        "requirements": [],
        "skills_required": [],
        "benefits": None,
        "language": "en",
        "posted_date": None,
        "deadline": None,
    }
