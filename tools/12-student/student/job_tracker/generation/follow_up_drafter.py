"""Post-interview follow-up email drafting."""

from __future__ import annotations


FOLLOW_UP_PROMPT = """Draft a professional post-interview follow-up email for a job application in Hong Kong.

Application Details:
- Company: {company}
- Position: {title}
- Application Stage: {stage}
- Notes: {notes}

Interview Details:
- Type: {interview_type}
- Date: {interview_date}
- Location: {location}
- Interviewer: {interviewer}
- Post-Interview Notes: {post_notes}

Guidelines:
- Thank the interviewer for their time
- Reference specific topics discussed (use the notes as hints)
- Reaffirm interest in the role
- Keep it concise and professional
- Appropriate for Hong Kong business culture

Write the follow-up email now:
"""


async def draft_follow_up(application: dict, interview: dict, llm) -> str:
    prompt = FOLLOW_UP_PROMPT.format(
        company=application.get("company", ""),
        title=application.get("title", ""),
        stage=application.get("stage", ""),
        notes=application.get("notes", "") or "",
        interview_type=interview.get("interview_type", ""),
        interview_date=interview.get("datetime", ""),
        location=interview.get("location", "") or "",
        interviewer=interview.get("interviewer", "") or "the interviewer",
        post_notes=interview.get("post_interview_notes", "") or "",
    )

    return await llm.generate(prompt)
