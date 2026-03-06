"""Generate personalized study plans based on weak areas."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

from student.interview_prep.tracking.weakness_analyzer import analyze_weaknesses


async def generate_study_plan(db_path: str | Path, llm) -> dict:
    weaknesses = analyze_weaknesses(db_path)

    with get_db(db_path) as conn:
        progress_rows = conn.execute("SELECT * FROM progress ORDER BY solve_rate ASC").fetchall()
    all_progress = [dict(r) for r in progress_rows]

    focus_topics = [w["topic"] for w in weaknesses[:5]] if weaknesses else ["arrays", "strings"]
    daily_problems = 3
    duration_days = 14

    prompt = (
        "Create a 14-day coding interview study plan for a student.\n\n"
        f"Weak areas (need most practice): {', '.join(focus_topics)}\n"
        f"All topic stats:\n"
    )
    for p in all_progress:
        prompt += f"  - {p['topic']}: {p.get('problems_solved', 0)}/{p.get('problems_attempted', 0)} solved ({p.get('solve_rate', 0):.0%})\n"

    prompt += (
        f"\nPlan {daily_problems} problems per day. "
        f"Format as a brief day-by-day plan. Be specific about which topics to cover each day. "
        f"Alternate between weak areas and review of stronger topics."
    )

    response = await llm.generate(prompt)
    plan_text = response if isinstance(response, str) else response.get("text", "")

    plan = {
        "focus_topics": focus_topics,
        "daily_problems": daily_problems,
        "duration_days": duration_days,
        "plan_details": plan_text,
    }

    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO study_plans (focus_topics, daily_problems, duration_days, plan_details)
               VALUES (?,?,?,?)""",
            (json.dumps(focus_topics), daily_problems, duration_days, plan_text),
        )

    return plan
