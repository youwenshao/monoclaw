"""LLM-powered cover letter generation."""

from __future__ import annotations

import json

COVER_LETTER_PROMPT = """Write a professional cover letter for a job application in Hong Kong.

Job Details:
- Title: {title}
- Company: {company}
- Requirements: {requirements}
- Key Skills: {skills}

Candidate Profile:
- Skills: {cv_skills}
- Education: {education}
- Experience: {experience}

Guidelines:
- Professional but personable tone
- Highlight relevant skills and experience that match the job requirements
- Show enthusiasm for the role and company
- Keep it concise (3-4 paragraphs)
- If the candidate is a fresh graduate, emphasise academic achievements and transferable skills
- End with a confident closing

Write the cover letter now:
"""


async def generate_cover_letter(job: dict, cv_profile: dict, llm) -> str:
    requirements = job.get("requirements", [])
    if isinstance(requirements, str):
        try:
            requirements = json.loads(requirements)
        except (json.JSONDecodeError, TypeError):
            requirements = [requirements]

    skills = job.get("skills_required", [])
    if isinstance(skills, str):
        try:
            skills = json.loads(skills)
        except (json.JSONDecodeError, TypeError):
            skills = [skills]

    cv_skills = cv_profile.get("skills", [])
    if isinstance(cv_skills, str):
        try:
            cv_skills = json.loads(cv_skills)
        except (json.JSONDecodeError, TypeError):
            cv_skills = [cv_skills]

    education = cv_profile.get("education", [])
    if isinstance(education, str):
        try:
            education = json.loads(education)
        except (json.JSONDecodeError, TypeError):
            education = [education]

    experience = cv_profile.get("experience", [])
    if isinstance(experience, str):
        try:
            experience = json.loads(experience)
        except (json.JSONDecodeError, TypeError):
            experience = [experience]

    prompt = COVER_LETTER_PROMPT.format(
        title=job.get("title", ""),
        company=job.get("company", ""),
        requirements=", ".join(requirements) if isinstance(requirements, list) else str(requirements),
        skills=", ".join(skills) if isinstance(skills, list) else str(skills),
        cv_skills=", ".join(cv_skills) if isinstance(cv_skills, list) else str(cv_skills),
        education=json.dumps(education, default=str)[:500],
        experience=json.dumps(experience, default=str)[:500],
    )

    return await llm.generate(prompt)
