"""Gap analysis between CV profile and job listing requirements."""

from __future__ import annotations

import json


def analyze_gaps(cv_profile: dict, job_listing: dict) -> dict:
    cv_skills = set(s.lower() for s in (cv_profile.get("skills") or []))

    jd_skills_raw = job_listing.get("skills_required") or []
    if isinstance(jd_skills_raw, str):
        try:
            jd_skills_raw = json.loads(jd_skills_raw)
        except (json.JSONDecodeError, TypeError):
            jd_skills_raw = [s.strip() for s in jd_skills_raw.split(",") if s.strip()]
    jd_skills = set(s.lower() for s in jd_skills_raw)

    missing = sorted(jd_skills - cv_skills)
    overlap = sorted(jd_skills & cv_skills)

    gap_score = len(missing) / len(jd_skills) if jd_skills else 0.0

    recommendations = _build_recommendations(missing, cv_profile, job_listing)

    return {
        "missing_skills": missing,
        "matched_skills": overlap,
        "skill_gap_score": round(gap_score, 3),
        "recommendations": recommendations,
    }


def _build_recommendations(
    missing: list[str],
    cv_profile: dict,
    job_listing: dict,
) -> list[str]:
    recs: list[str] = []

    if not missing:
        recs.append("Your skills align well with this role. Focus on demonstrating depth in interviews.")
        return recs

    technical = [s for s in missing if _is_technical(s)]
    soft = [s for s in missing if not _is_technical(s)]

    if technical:
        recs.append(
            f"Consider gaining experience in: {', '.join(technical[:5])}. "
            "Online courses or personal projects can help bridge this gap."
        )

    if soft:
        recs.append(
            f"Highlight transferable experience related to: {', '.join(soft[:5])}."
        )

    jt = job_listing.get("job_type", "")
    if jt == "graduate_programme":
        recs.append("Graduate programmes value potential — emphasise academic projects, internships, and learning agility.")
    elif jt == "internship":
        recs.append("For internships, coursework and side projects can compensate for missing professional experience.")

    if len(missing) > len(cv_profile.get("skills", [])) * 0.5:
        recs.append("This role has a significant skill gap. Consider upskilling before applying or targeting closer-fit roles.")

    return recs


TECHNICAL_KEYWORDS = {
    "python", "java", "javascript", "typescript", "sql", "r", "c++", "c#", "go",
    "rust", "swift", "kotlin", "react", "angular", "vue", "nodejs", "django",
    "flask", "spring", "docker", "kubernetes", "aws", "azure", "gcp", "git",
    "linux", "terraform", "jenkins", "ci/cd", "mongodb", "postgresql", "redis",
    "elasticsearch", "graphql", "rest", "api", "html", "css", "sass", "webpack",
    "tableau", "powerbi", "excel", "sas", "spss", "matlab", "stata",
    "tensorflow", "pytorch", "pandas", "numpy", "scikit-learn", "spark",
    "hadoop", "kafka", "airflow", "dbt", "figma", "sketch", "photoshop",
}


def _is_technical(skill: str) -> bool:
    return skill.lower() in TECHNICAL_KEYWORDS
