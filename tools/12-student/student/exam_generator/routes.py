"""ExamGenerator FastAPI routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/exam-generator", tags=["ExamGenerator"])

templates = Jinja2Templates(directory="student/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "exam-generator", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def exam_generator_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        total_exams = conn.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
        total_attempts = conn.execute("SELECT COUNT(*) FROM exam_attempts").fetchone()[0]
        avg_row = conn.execute(
            "SELECT AVG(percentage) FROM exam_attempts WHERE status = 'graded'"
        ).fetchone()
        avg_score = round(avg_row[0], 1) if avg_row[0] is not None else 0

    return templates.TemplateResponse(
        "exam_generator/index.html",
        _ctx(request, total_exams=total_exams, total_attempts=total_attempts, avg_score=avg_score),
    )


# ── Exams ──────────────────────────────────────────────────────────────────

class CreateExamRequest(BaseModel):
    course_id: int
    title: str
    generation_source: str
    question_count: int = 10
    time_limit_minutes: int = 60
    scope_config: dict[str, Any] | None = None
    difficulty_distribution: dict[str, float] | None = None
    question_types: list[str] | None = None


@router.post("/exams")
async def create_exam(request: Request, body: CreateExamRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO exams
               (course_id, title, generation_source, scope_config, question_count, time_limit_minutes)
               VALUES (?,?,?,?,?,?)""",
            (body.course_id, body.title, body.generation_source,
             json.dumps(body.scope_config or {}), body.question_count, body.time_limit_minutes),
        )
        exam_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="exam-generator",
        summary=f"Exam '{body.title}' created ({body.question_count} questions, {body.time_limit_minutes}min)",
    )

    return {"exam_id": exam_id, "status": "generating"}


@router.post("/exams/{exam_id}/generate")
async def generate_exam_questions(request: Request, exam_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]
    llm = request.app.state.llm

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Exam not found")

    exam = dict(row)
    scope_config = json.loads(exam.get("scope_config") or "{}")
    diff_dist = scope_config.get("difficulty_distribution", {"easy": 0.3, "medium": 0.5, "hard": 0.2})
    q_types = scope_config.get("question_types", ["mcq", "short_answer", "long_answer"])

    from student.exam_generator.generation.custom_generator import generate_custom
    questions = generate_custom(
        topic=exam["title"],
        requirements=json.dumps(scope_config),
        question_count=exam["question_count"],
        question_types=q_types,
        llm=llm,
    )

    from student.exam_generator.exam.exam_builder import build_exam
    structured = build_exam(questions, {
        "question_count": exam["question_count"],
        "time_limit_minutes": exam["time_limit_minutes"],
    })

    with get_db(db) as conn:
        for i, q in enumerate(structured["questions"]):
            conn.execute(
                """INSERT INTO exam_questions
                   (exam_id, question_index, section, question_type, question_text, options,
                    correct_answer, rubric, source_chunks, difficulty, topic, points, bloom_level)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (exam_id, i + 1, q.get("section", "A"), q["question_type"],
                 q["question_text"], json.dumps(q.get("options") or []),
                 q.get("correct_answer", ""), q.get("rubric", ""),
                 json.dumps(q.get("source_chunks") or []),
                 q.get("difficulty", "medium"), q.get("topic", ""),
                 q.get("points", 1.0), q.get("bloom_level", "understand")),
            )
        conn.execute("UPDATE exams SET status = 'ready' WHERE id = ?", (exam_id,))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="exam-generator",
        summary=f"Generated {len(structured['questions'])} questions for exam #{exam_id}",
    )

    return {"exam_id": exam_id, "questions_generated": len(structured["questions"]), "status": "ready"}


@router.get("/exams/{exam_id}")
async def get_exam(request: Request, exam_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        exam_row = conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone()
        if not exam_row:
            raise HTTPException(status_code=404, detail="Exam not found")
        questions = [dict(r) for r in conn.execute(
            "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_index",
            (exam_id,),
        ).fetchall()]

    exam = dict(exam_row)
    for q in questions:
        if q.get("options"):
            q["options"] = json.loads(q["options"])

    return {"exam": exam, "questions": questions}


# ── Exam attempts ──────────────────────────────────────────────────────────

@router.post("/exams/{exam_id}/start")
async def start_exam(request: Request, exam_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]

    from student.exam_generator.exam.exam_engine import start_exam as engine_start
    attempt_id = engine_start(exam_id, db)

    with get_db(db) as conn:
        conn.execute("UPDATE exams SET status = 'in_progress' WHERE id = ?", (exam_id,))

    return {"attempt_id": attempt_id, "status": "in_progress"}


class AnswerRequest(BaseModel):
    question_id: int
    student_answer: str
    flagged_for_review: bool = False


@router.post("/attempts/{attempt_id}/answer")
async def save_answer(request: Request, attempt_id: int, body: AnswerRequest) -> dict[str, str]:
    db = request.app.state.db_paths["exam_generator"]

    from student.exam_generator.exam.answer_manager import save_answer as mgr_save
    mgr_save(attempt_id, body.question_id, body.student_answer, body.flagged_for_review, db)

    return {"status": "saved"}


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(request: Request, attempt_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]
    llm = request.app.state.llm

    from student.exam_generator.exam.exam_engine import submit_exam
    result = submit_exam(attempt_id, db)

    from student.exam_generator.grading.feedback_engine import grade_exam
    grading = grade_exam(attempt_id, db, llm)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="exam-generator",
        summary=f"Exam attempt #{attempt_id} graded: {grading.get('percentage', 0):.0f}% ({grading.get('letter_grade', 'N/A')})",
    )

    return {"attempt_id": attempt_id, **result, **grading}


@router.get("/attempts/{attempt_id}/results")
async def get_results(request: Request, attempt_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        attempt = conn.execute("SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)).fetchone()
        if not attempt:
            raise HTTPException(status_code=404, detail="Attempt not found")
        answers = [dict(r) for r in conn.execute(
            """SELECT aa.*, eq.question_text, eq.question_type, eq.correct_answer,
                      eq.options, eq.topic, eq.difficulty, eq.bloom_level, eq.points as max_pts
               FROM attempt_answers aa
               JOIN exam_questions eq ON aa.question_id = eq.id
               WHERE aa.attempt_id = ? ORDER BY eq.question_index""",
            (attempt_id,),
        ).fetchall()]

    attempt_data = dict(attempt)
    for a in answers:
        if a.get("options"):
            a["options"] = json.loads(a["options"])
    attempt_data["topic_breakdown"] = json.loads(attempt_data.get("topic_breakdown") or "{}")
    attempt_data["difficulty_breakdown"] = json.loads(attempt_data.get("difficulty_breakdown") or "{}")

    return {"attempt": attempt_data, "answers": answers}


# ── Discussion ─────────────────────────────────────────────────────────────

class DiscussionRequest(BaseModel):
    question_id: int
    message: str


@router.post("/attempts/{attempt_id}/discuss")
async def post_discussion(request: Request, attempt_id: int, body: DiscussionRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]
    llm = request.app.state.llm

    from student.exam_generator.discussion.discussion_engine import get_mona_response, save_message
    save_message(attempt_id, body.question_id, "student", body.message, db)

    mona_reply = get_mona_response(attempt_id, body.question_id, body.message, db, llm)
    save_message(attempt_id, body.question_id, "mona", mona_reply, db)

    return {"role": "mona", "message": mona_reply}


@router.get("/attempts/{attempt_id}/discussions")
async def get_discussions(request: Request, attempt_id: int, question_id: int | None = None) -> list[dict]:
    db = request.app.state.db_paths["exam_generator"]

    query = "SELECT * FROM exam_discussions WHERE attempt_id = ?"
    params: list[Any] = [attempt_id]
    if question_id is not None:
        query += " AND question_id = ?"
        params.append(question_id)
    query += " ORDER BY timestamp ASC"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Past papers ────────────────────────────────────────────────────────────

@router.post("/past-papers/upload")
async def upload_past_paper(request: Request, file: UploadFile, course_id: int = 0) -> dict[str, Any]:
    db = request.app.state.db_paths["exam_generator"]
    workspace: Path = request.app.state.workspace

    upload_dir = workspace / "past_papers"
    upload_dir.mkdir(parents=True, exist_ok=True)
    dest = upload_dir / (file.filename or "paper.pdf")

    content = await file.read()
    dest.write_bytes(content)

    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO past_papers (course_id, filename, file_path) VALUES (?,?,?)",
            (course_id, file.filename, str(dest)),
        )
        paper_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="exam-generator",
        summary=f"Past paper '{file.filename}' uploaded",
    )

    return {"paper_id": paper_id, "file_path": str(dest)}


# ── History & analytics ────────────────────────────────────────────────────

@router.get("/history")
async def exam_history(request: Request) -> list[dict]:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT ea.*, e.title as exam_title, e.course_id
               FROM exam_attempts ea
               JOIN exams e ON ea.exam_id = e.id
               ORDER BY ea.started_at DESC""",
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/analytics/topics")
async def topic_analytics(request: Request) -> list[dict]:
    db = request.app.state.db_paths["exam_generator"]

    from student.exam_generator.analytics.weakness_analyzer import analyze_weaknesses
    return analyze_weaknesses(db)


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/exam-wizard/partial", response_class=HTMLResponse)
async def exam_wizard_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]
    study_db = request.app.state.db_paths["study_buddy"]

    with get_db(study_db) as conn:
        courses = [dict(r) for r in conn.execute("SELECT * FROM courses ORDER BY course_code").fetchall()]

    with get_db(db) as conn:
        past_papers = [dict(r) for r in conn.execute("SELECT * FROM past_papers ORDER BY uploaded_at DESC").fetchall()]

    return templates.TemplateResponse(
        "exam_generator/partials/exam_wizard.html",
        {"request": request, "courses": courses, "past_papers": past_papers},
    )


@router.get("/exam-interface/partial", response_class=HTMLResponse)
async def exam_interface_partial(request: Request, exam_id: int, attempt_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        exam = dict(conn.execute("SELECT * FROM exams WHERE id = ?", (exam_id,)).fetchone() or {})
        questions = [dict(r) for r in conn.execute(
            "SELECT * FROM exam_questions WHERE exam_id = ? ORDER BY question_index",
            (exam_id,),
        ).fetchall()]
        answers = [dict(r) for r in conn.execute(
            "SELECT * FROM attempt_answers WHERE attempt_id = ?",
            (attempt_id,),
        ).fetchall()]

    for q in questions:
        if q.get("options"):
            q["options"] = json.loads(q["options"])

    answered_ids = {a["question_id"] for a in answers}

    return templates.TemplateResponse(
        "exam_generator/partials/exam_interface.html",
        {"request": request, "exam": exam, "questions": questions,
         "answers": answers, "answered_ids": answered_ids,
         "attempt_id": attempt_id},
    )


@router.get("/grading-view/partial", response_class=HTMLResponse)
async def grading_view_partial(request: Request, attempt_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        attempt = dict(conn.execute("SELECT * FROM exam_attempts WHERE id = ?", (attempt_id,)).fetchone() or {})
        answers = [dict(r) for r in conn.execute(
            """SELECT aa.*, eq.question_text, eq.question_type, eq.correct_answer,
                      eq.options, eq.topic, eq.difficulty, eq.bloom_level
               FROM attempt_answers aa
               JOIN exam_questions eq ON aa.question_id = eq.id
               WHERE aa.attempt_id = ? ORDER BY eq.question_index""",
            (attempt_id,),
        ).fetchall()]

    for a in answers:
        if a.get("options"):
            a["options"] = json.loads(a["options"])
    attempt["topic_breakdown"] = json.loads(attempt.get("topic_breakdown") or "{}")
    attempt["difficulty_breakdown"] = json.loads(attempt.get("difficulty_breakdown") or "{}")

    return templates.TemplateResponse(
        "exam_generator/partials/grading_view.html",
        {"request": request, "attempt": attempt, "answers": answers},
    )


@router.get("/discussion-chat/partial", response_class=HTMLResponse)
async def discussion_chat_partial(request: Request, attempt_id: int, question_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        messages = [dict(r) for r in conn.execute(
            "SELECT * FROM exam_discussions WHERE attempt_id = ? AND question_id = ? ORDER BY timestamp ASC",
            (attempt_id, question_id),
        ).fetchall()]
        question = dict(conn.execute("SELECT * FROM exam_questions WHERE id = ?", (question_id,)).fetchone() or {})

    return templates.TemplateResponse(
        "exam_generator/partials/discussion_chat.html",
        {"request": request, "messages": messages, "question": question,
         "attempt_id": attempt_id, "question_id": question_id},
    )


@router.get("/exam-history/partial", response_class=HTMLResponse)
async def exam_history_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    with get_db(db) as conn:
        attempts = [dict(r) for r in conn.execute(
            """SELECT ea.*, e.title as exam_title, e.course_id
               FROM exam_attempts ea JOIN exams e ON ea.exam_id = e.id
               ORDER BY ea.started_at DESC""",
        ).fetchall()]

    return templates.TemplateResponse(
        "exam_generator/partials/exam_history.html",
        {"request": request, "attempts": attempts},
    )


@router.get("/topic-breakdown/partial", response_class=HTMLResponse)
async def topic_breakdown_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["exam_generator"]

    from student.exam_generator.analytics.weakness_analyzer import analyze_weaknesses
    topics = analyze_weaknesses(db)

    return templates.TemplateResponse(
        "exam_generator/partials/topic_breakdown.html",
        {"request": request, "topics": topics},
    )
