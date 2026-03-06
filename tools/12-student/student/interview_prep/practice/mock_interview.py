"""Mock interview session management."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from openclaw_shared.database import get_db

from student.interview_prep.problems.problem_loader import get_random_problems


def start_mock(db_path: str | Path, difficulty: str | None = None) -> dict:
    problems = get_random_problems(db_path, count=2, difficulty=difficulty)
    if len(problems) < 2:
        problems = get_random_problems(db_path, count=2)

    problem_ids = [p["id"] for p in problems]

    with get_db(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO mock_interviews (started_at, problems) VALUES (?, ?)",
            (datetime.utcnow().isoformat(), json.dumps(problem_ids)),
        )
        mock_id = cursor.lastrowid

    return {
        "mock_id": mock_id,
        "problems": problems,
        "time_limit_minutes": 45,
        "started_at": datetime.utcnow().isoformat(),
    }


async def complete_mock(
    mock_id: int,
    results: list[dict],
    db_path: str | Path,
    llm,
) -> dict:
    total_passed = sum(r.get("passed_tests", 0) for r in results)
    total_tests = sum(r.get("total_tests", 0) for r in results)
    score = (total_passed / total_tests * 100) if total_tests > 0 else 0

    feedback_prompt = (
        f"A student completed a mock coding interview.\n"
        f"Results: {total_passed}/{total_tests} test cases passed across {len(results)} problems.\n"
        f"Score: {score:.0f}%\n\n"
        f"Problem results:\n"
    )
    for i, r in enumerate(results):
        feedback_prompt += (
            f"Problem {i + 1}: {r.get('title', 'Unknown')} - "
            f"{r.get('passed_tests', 0)}/{r.get('total_tests', 0)} passed, "
            f"time: {r.get('time_seconds', 0)}s\n"
        )
    feedback_prompt += "\nProvide brief, constructive feedback (3-4 sentences)."

    response = await llm.generate(feedback_prompt)
    feedback = response if isinstance(response, str) else response.get("text", "")

    with get_db(db_path) as conn:
        conn.execute(
            """UPDATE mock_interviews
               SET completed_at = ?, results = ?, overall_score = ?, feedback = ?
               WHERE id = ?""",
            (datetime.utcnow().isoformat(), json.dumps(results), score, feedback, mock_id),
        )

    return {
        "mock_id": mock_id,
        "score": score,
        "total_passed": total_passed,
        "total_tests": total_tests,
        "feedback": feedback,
    }
