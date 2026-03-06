"""LLM-powered job description structuring and source detection."""

from __future__ import annotations

import json
import re
from urllib.parse import urlparse


STRUCTURE_PROMPT = """Extract structured data from this job description. Return valid JSON only.

Fields:
- title (str)
- company (str)
- salary_min (float or null, monthly HKD)
- salary_max (float or null, monthly HKD)
- location (str)
- district (str or null, HK district)
- job_type (one of: full_time, part_time, contract, internship, graduate_programme)
- industry (str)
- requirements (list of strings)
- skills_required (list of strings, technical/soft skills as lowercase keywords)
- benefits (str or null)
- language (str, "en" or "zh" or "bilingual")
- posted_date (str YYYY-MM-DD or null)
- deadline (str YYYY-MM-DD or null)

Job Description:
{text}
"""

SOURCE_DOMAINS: dict[str, str] = {
    "ctgoodjobs.hk": "ctgoodjobs",
    "jobsdb.com": "jobsdb",
    "hk.jobsdb.com": "jobsdb",
    "linkedin.com": "linkedin",
    "hk.linkedin.com": "linkedin",
}


def detect_source(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return "other"
    host = host.lower().removeprefix("www.")
    for domain, source in SOURCE_DOMAINS.items():
        if host == domain or host.endswith("." + domain):
            return source
    return "company_site"


async def structure_jd(raw_text: str, llm) -> dict:
    prompt = STRUCTURE_PROMPT.format(text=raw_text[:8000])
    response = await llm.generate(prompt)

    json_match = re.search(r"\{[\s\S]*\}", response)
    if not json_match:
        return _fallback_parse(raw_text)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return _fallback_parse(raw_text)

    data.setdefault("title", "")
    data.setdefault("company", "")
    data.setdefault("salary_min", None)
    data.setdefault("salary_max", None)
    data.setdefault("location", "Hong Kong")
    data.setdefault("district", None)
    data.setdefault("job_type", "full_time")
    data.setdefault("industry", "")
    data.setdefault("requirements", [])
    data.setdefault("skills_required", [])
    data.setdefault("benefits", None)
    data.setdefault("language", "en")
    data.setdefault("posted_date", None)
    data.setdefault("deadline", None)

    if isinstance(data["requirements"], str):
        data["requirements"] = [data["requirements"]]
    if isinstance(data["skills_required"], str):
        data["skills_required"] = [s.strip().lower() for s in data["skills_required"].split(",")]

    return data


def _fallback_parse(text: str) -> dict:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return {
        "title": lines[0] if lines else "",
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
