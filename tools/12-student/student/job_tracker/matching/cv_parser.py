"""CV parsing: extract text from PDF/DOCX and structure via LLM."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger("openclaw.student.job_tracker.cv_parser")


def parse_cv(file_path: str) -> dict:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        text = _extract_pdf(path)
    elif suffix in (".docx", ".doc"):
        text = _extract_docx(path)
    else:
        text = path.read_text(encoding="utf-8", errors="replace")

    return {"text": text, "file_path": str(path), "format": suffix.lstrip(".")}


def _extract_pdf(path: Path) -> str:
    try:
        import fitz
        doc = fitz.open(str(path))
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception:
        logger.exception("Failed to extract PDF: %s", path)
        return ""


def _extract_docx(path: Path) -> str:
    try:
        import docx
        doc = docx.Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception:
        logger.exception("Failed to extract DOCX: %s", path)
        return ""


EXTRACT_PROMPT = """Extract structured CV data from the following text. Return valid JSON only.

Fields:
- skills (list of strings, lowercase technical/soft skills)
- education (list of objects with: institution, degree, field, year)
- experience (list of objects with: company, title, duration, highlights)
- keywords (list of strings, important terms for ATS matching)

CV Text:
{text}
"""


async def extract_cv_data(text: str, llm) -> dict:
    prompt = EXTRACT_PROMPT.format(text=text[:6000])
    response = await llm.generate(prompt)

    json_match = re.search(r"\{[\s\S]*\}", response)
    if not json_match:
        return _fallback_extract(text)

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError:
        return _fallback_extract(text)

    data.setdefault("skills", [])
    data.setdefault("education", [])
    data.setdefault("experience", [])
    data.setdefault("keywords", [])

    data["skills"] = [s.lower().strip() for s in data["skills"] if isinstance(s, str)]
    data["keywords"] = [k.lower().strip() for k in data["keywords"] if isinstance(k, str)]

    return data


def _fallback_extract(text: str) -> dict:
    words = set(re.findall(r"\b[a-zA-Z]{2,}\b", text.lower()))
    common_skills = {
        "python", "java", "javascript", "sql", "excel", "r", "c++", "html", "css",
        "react", "nodejs", "docker", "aws", "git", "linux", "tableau", "powerbi",
        "tensorflow", "pytorch", "pandas", "numpy", "agile", "scrum", "jira",
    }
    found_skills = sorted(words & common_skills)
    return {
        "skills": found_skills,
        "education": [],
        "experience": [],
        "keywords": found_skills[:20],
    }
