"""InterviewPrep FastAPI routes."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/interview-prep", tags=["InterviewPrep"])

templates = Jinja2Templates(directory="student/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "interview-prep", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def interview_prep_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]

    with get_db(db) as conn:
        total_problems = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
        solved = conn.execute(
            "SELECT COUNT(DISTINCT problem_id) FROM attempts WHERE is_correct = 1"
        ).fetchone()[0]
        weak_count = conn.execute(
            "SELECT COUNT(*) FROM progress WHERE solve_rate < 0.3 OR strength_level = 'weak'"
        ).fetchone()[0]

    from student.interview_prep.tracking.progress_tracker import get_streak
    streak = get_streak(db)

    return templates.TemplateResponse(
        "interview_prep/index.html",
        _ctx(
            request,
            total_problems=total_problems,
            solved=solved,
            streak=streak,
            weak_count=weak_count,
        ),
    )


# ── Problems ───────────────────────────────────────────────────────────────

@router.get("/problems")
async def list_problems(
    request: Request,
    topic: str | None = None,
    difficulty: str | None = None,
    status: str | None = None,
) -> list[dict]:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problems
    problems = get_problems(db, topic=topic, difficulty=difficulty)

    if status:
        with get_db(db) as conn:
            solved_ids = {
                r[0] for r in conn.execute(
                    "SELECT DISTINCT problem_id FROM attempts WHERE is_correct = 1"
                ).fetchall()
            }
        if status == "solved":
            problems = [p for p in problems if p["id"] in solved_ids]
        elif status == "unsolved":
            problems = [p for p in problems if p["id"] not in solved_ids]

    return problems


@router.get("/problems/{problem_id}")
async def get_problem(request: Request, problem_id: int) -> dict:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")
    return problem


# ── Code execution ─────────────────────────────────────────────────────────

class RunCodeRequest(BaseModel):
    code: str
    language: str


@router.post("/problems/{problem_id}/run")
async def run_code(request: Request, problem_id: int, body: RunCodeRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    test_cases = problem.get("test_cases", [])
    if isinstance(test_cases, str):
        test_cases = json.loads(test_cases)

    from student.interview_prep.problems.test_cases import run_test_cases
    result = run_test_cases(body.code, body.language, test_cases)

    is_correct = result["passed"] == result["total"] and result["total"] > 0

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO attempts
               (problem_id, code, language, passed_tests, total_tests, is_correct, submitted_at)
               VALUES (?,?,?,?,?,?,?)""",
            (problem_id, body.code, body.language, result["passed"],
             result["total"], is_correct, datetime.utcnow().isoformat()),
        )

    from student.interview_prep.tracking.progress_tracker import update_progress
    update_progress(problem, {"is_correct": is_correct, "hints_used": 0}, db)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="interview-prep",
        summary=f"Code submitted for '{problem['title']}': {result['passed']}/{result['total']} passed",
    )

    return {"problem_id": problem_id, "is_correct": is_correct, **result}


# ── Hints ──────────────────────────────────────────────────────────────────

class HintRequest(BaseModel):
    hint_level: int = 1


@router.post("/problems/{problem_id}/hint")
async def get_hint_route(request: Request, problem_id: int, body: HintRequest) -> dict[str, str]:
    db = request.app.state.db_paths["interview_prep"]
    llm = request.app.state.llm

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    from student.interview_prep.practice.hint_engine import get_hint
    hint = await get_hint(problem, body.hint_level, llm)
    return {"hint_level": body.hint_level, "hint": hint}


# ── Solution explanation ───────────────────────────────────────────────────

class ExplainRequest(BaseModel):
    student_code: str | None = None


@router.post("/problems/{problem_id}/explain")
async def explain_solution_route(request: Request, problem_id: int, body: ExplainRequest) -> dict[str, str]:
    db = request.app.state.db_paths["interview_prep"]
    llm = request.app.state.llm

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)
    if not problem:
        raise HTTPException(status_code=404, detail="Problem not found")

    from student.interview_prep.practice.solution_explainer import explain_solution
    explanation = await explain_solution(problem, body.student_code, llm)
    return {"explanation": explanation}


# ── Mock interviews ────────────────────────────────────────────────────────

class StartMockRequest(BaseModel):
    difficulty: str | None = None


@router.post("/mock-interviews/start")
async def start_mock_interview(request: Request, body: StartMockRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.practice.mock_interview import start_mock
    result = start_mock(db, difficulty=body.difficulty)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="interview-prep",
        summary=f"Mock interview #{result['mock_id']} started ({len(result['problems'])} problems)",
    )

    return result


class SubmitMockRequest(BaseModel):
    results: list[dict]


@router.post("/mock-interviews/{mock_id}/submit")
async def submit_mock_interview(request: Request, mock_id: int, body: SubmitMockRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["interview_prep"]
    llm = request.app.state.llm

    from student.interview_prep.practice.mock_interview import complete_mock
    result = await complete_mock(mock_id, body.results, db, llm)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="interview-prep",
        summary=f"Mock interview #{mock_id} completed: {result['score']:.0f}%",
    )

    return result


@router.get("/mock-interviews/{mock_id}/results")
async def get_mock_results(request: Request, mock_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["interview_prep"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM mock_interviews WHERE id = ?", (mock_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Mock interview not found")

    data = dict(row)
    for field in ("problems", "results"):
        if isinstance(data.get(field), str):
            try:
                data[field] = json.loads(data[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return data


# ── Progress ───────────────────────────────────────────────────────────────

@router.get("/progress")
async def get_progress(request: Request) -> list[dict]:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.tracking.progress_tracker import get_topic_progress
    return get_topic_progress(db)


@router.get("/progress/study-plan")
async def get_study_plan(request: Request) -> dict[str, Any]:
    db = request.app.state.db_paths["interview_prep"]
    llm = request.app.state.llm

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM study_plans ORDER BY id DESC LIMIT 1").fetchone()

    if row:
        plan = dict(row)
        if isinstance(plan.get("focus_topics"), str):
            try:
                plan["focus_topics"] = json.loads(plan["focus_topics"])
            except (json.JSONDecodeError, TypeError):
                pass
        return plan

    from student.interview_prep.tracking.study_plan import generate_study_plan
    return await generate_study_plan(db, llm)


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/problem-browser/partial", response_class=HTMLResponse)
async def problem_browser_partial(
    request: Request,
    topic: str | None = None,
    difficulty: str | None = None,
) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problems
    problems = get_problems(db, topic=topic, difficulty=difficulty)

    with get_db(db) as conn:
        solved_ids = {
            r[0] for r in conn.execute(
                "SELECT DISTINCT problem_id FROM attempts WHERE is_correct = 1"
            ).fetchall()
        }

    for p in problems:
        p["solved"] = p["id"] in solved_ids

    return templates.TemplateResponse(
        "interview_prep/partials/problem_browser.html",
        {"request": request, "problems": problems},
    )


@router.get("/code-editor/partial", response_class=HTMLResponse)
async def code_editor_partial(request: Request, problem_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)

    return templates.TemplateResponse(
        "interview_prep/partials/code_editor.html",
        {"request": request, "problem": problem},
    )


@router.get("/hint-panel/partial", response_class=HTMLResponse)
async def hint_panel_partial(request: Request, problem_id: int, level: int = 1) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]
    llm = request.app.state.llm

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    from student.interview_prep.practice.hint_engine import get_hint

    problem = load_problem(db, problem_id)
    hint = await get_hint(problem, level, llm) if problem else ""

    return templates.TemplateResponse(
        "interview_prep/partials/hint_panel.html",
        {"request": request, "hint": hint, "level": level, "problem_id": problem_id},
    )


@router.get("/solution-view/partial", response_class=HTMLResponse)
async def solution_view_partial(request: Request, problem_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.problems.problem_loader import get_problem as load_problem
    problem = load_problem(db, problem_id)

    return templates.TemplateResponse(
        "interview_prep/partials/solution_view.html",
        {"request": request, "problem": problem},
    )


@router.get("/progress-dashboard/partial", response_class=HTMLResponse)
async def progress_dashboard_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["interview_prep"]

    from student.interview_prep.tracking.progress_tracker import get_topic_progress, get_streak
    from student.interview_prep.tracking.weakness_analyzer import analyze_weaknesses

    progress = get_topic_progress(db)
    streak = get_streak(db)
    weaknesses = analyze_weaknesses(db)

    return templates.TemplateResponse(
        "interview_prep/partials/progress_dashboard.html",
        {"request": request, "progress": progress, "streak": streak, "weaknesses": weaknesses},
    )
