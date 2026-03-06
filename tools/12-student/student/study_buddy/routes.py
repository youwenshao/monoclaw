"""StudyBuddy FastAPI routes."""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/study-buddy", tags=["StudyBuddy"])

templates = Jinja2Templates(directory="student/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "study-buddy", **extra}


# ── Page ───────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def study_buddy_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["study_buddy"]
    now = datetime.now().isoformat()

    with get_db(db) as conn:
        course_count = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        flashcards_due = conn.execute(
            "SELECT COUNT(*) FROM flashcards WHERE next_review IS NULL OR next_review <= ?",
            (now,),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "study_buddy/index.html",
        _ctx(
            request,
            course_count=course_count,
            doc_count=doc_count,
            flashcards_due=flashcards_due,
        ),
    )


# ── Courses ────────────────────────────────────────────────────────────────


class CreateCourseRequest(BaseModel):
    course_code: str
    course_name: str
    semester: str = ""
    instructor: str = ""


@router.post("/courses")
async def create_course(request: Request, body: CreateCourseRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["study_buddy"]

    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO courses (course_code, course_name, semester, instructor) VALUES (?, ?, ?, ?)",
            (body.course_code, body.course_name, body.semester, body.instructor),
        )
        course_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="study-buddy",
        summary=f"Course {body.course_code} created",
    )

    return {"course_id": course_id, "course_code": body.course_code}


@router.get("/courses")
async def list_courses(request: Request) -> list[dict]:
    db = request.app.state.db_paths["study_buddy"]
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM courses ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── Documents ──────────────────────────────────────────────────────────────


@router.post("/upload")
async def upload_document(request: Request, file: UploadFile, course_id: int = 0) -> dict[str, Any]:
    db = request.app.state.db_paths["study_buddy"]
    workspace: Path = request.app.state.workspace

    docs_dir = workspace / "documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    dest = docs_dir / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    ext = dest.suffix.lower().lstrip(".")
    doc_type = ext if ext in ("pdf", "pptx", "docx", "txt", "md") else "txt"

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO documents
               (course_id, filename, file_path, doc_type, title, indexed)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (course_id, file.filename, str(dest), doc_type, dest.stem, False),
        )
        doc_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="study-buddy",
        summary=f"Document '{file.filename}' uploaded, indexing queued",
        details=json.dumps({"document_id": doc_id, "course_id": course_id}),
    )

    return {"document_id": doc_id, "filename": file.filename, "status": "uploaded"}


@router.get("/documents")
async def list_documents(request: Request, course_id: int = 0) -> list[dict]:
    db = request.app.state.db_paths["study_buddy"]
    query = "SELECT * FROM documents"
    params: list[Any] = []
    if course_id:
        query += " WHERE course_id = ?"
        params.append(course_id)
    query += " ORDER BY added_at DESC"
    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Q&A ────────────────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    query_text: str
    course_id: int | None = None


@router.post("/query")
async def qa_query(request: Request, body: QueryRequest) -> dict[str, Any]:
    from student.study_buddy.indexing.chroma_store import get_chroma_client
    from student.study_buddy.retrieval.qa_engine import answer

    db = request.app.state.db_paths["study_buddy"]
    chroma_client = get_chroma_client(str(request.app.state.chroma_dir))
    llm = request.app.state.llm

    result = await answer(body.query_text, body.course_id, db, chroma_client, llm)

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO queries (query_text, course_id, answer_text, cited_chunks) VALUES (?, ?, ?, ?)",
            (body.query_text, body.course_id, result["answer"], json.dumps(result["citations"])),
        )

    return result


# ── Flashcards ─────────────────────────────────────────────────────────────


class GenerateFlashcardsRequest(BaseModel):
    document_id: int


@router.post("/flashcards/generate")
async def generate_flashcards_route(request: Request, body: GenerateFlashcardsRequest) -> dict[str, Any]:
    from student.study_buddy.indexing.chroma_store import get_chroma_client
    from student.study_buddy.study.flashcard_generator import generate_flashcards

    db = request.app.state.db_paths["study_buddy"]
    chroma_client = get_chroma_client(str(request.app.state.chroma_dir))
    llm = request.app.state.llm

    with get_db(db) as conn:
        doc = conn.execute("SELECT course_id FROM documents WHERE id = ?", (body.document_id,)).fetchone()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    cards = await generate_flashcards(body.document_id, db, chroma_client, llm)

    with get_db(db) as conn:
        for card in cards:
            conn.execute(
                """INSERT INTO flashcards (course_id, document_id, question, answer, difficulty)
                   VALUES (?, ?, ?, ?, ?)""",
                (doc[0], body.document_id, card["question"], card["answer"], card.get("difficulty", "medium")),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="study-buddy",
        summary=f"Generated {len(cards)} flashcards from document #{body.document_id}",
    )

    return {"generated": len(cards), "flashcards": cards}


@router.get("/flashcards")
async def list_flashcards(request: Request, course_id: int = 0, due: bool = False) -> list[dict]:
    db = request.app.state.db_paths["study_buddy"]
    query = "SELECT * FROM flashcards"
    conditions: list[str] = []
    params: list[Any] = []

    if course_id:
        conditions.append("course_id = ?")
        params.append(course_id)
    if due:
        now = datetime.now().isoformat()
        conditions.append("(next_review IS NULL OR next_review <= ?)")
        params.append(now)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY next_review ASC NULLS FIRST"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


class ReviewFlashcardRequest(BaseModel):
    difficulty: str


@router.post("/flashcards/{card_id}/review")
async def review_flashcard(request: Request, card_id: int, body: ReviewFlashcardRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["study_buddy"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM flashcards WHERE id = ?", (card_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Flashcard not found")

    card = dict(row)
    review_count = (card.get("review_count") or 0) + 1
    now = datetime.now()

    intervals = {"easy": 7, "medium": 3, "hard": 1}
    base_days = intervals.get(body.difficulty, 3)
    multiplier = min(review_count, 5)
    next_review = now + timedelta(days=base_days * multiplier)

    with get_db(db) as conn:
        conn.execute(
            """UPDATE flashcards
               SET review_count = ?, last_reviewed = ?, next_review = ?, difficulty = ?
               WHERE id = ?""",
            (review_count, now.isoformat(), next_review.isoformat(), body.difficulty, card_id),
        )

    return {
        "card_id": card_id,
        "review_count": review_count,
        "next_review": next_review.isoformat(),
    }


# ── Summary ────────────────────────────────────────────────────────────────


class GenerateSummaryRequest(BaseModel):
    document_id: int
    detail_level: str = "detailed"


@router.post("/summary/generate")
async def generate_summary_route(request: Request, body: GenerateSummaryRequest) -> dict[str, str]:
    from student.study_buddy.indexing.chroma_store import get_chroma_client
    from student.study_buddy.study.summary_generator import generate_summary

    db = request.app.state.db_paths["study_buddy"]
    chroma_client = get_chroma_client(str(request.app.state.chroma_dir))
    llm = request.app.state.llm

    summary = await generate_summary(body.document_id, body.detail_level, db, chroma_client, llm)
    return {"summary": summary, "detail_level": body.detail_level}


# ── Search ─────────────────────────────────────────────────────────────────


@router.get("/search")
async def semantic_search(request: Request, query: str, course_id: int | None = None) -> list[dict]:
    from student.study_buddy.indexing.chroma_store import get_chroma_client
    from student.study_buddy.retrieval.search_engine import search

    db = request.app.state.db_paths["study_buddy"]
    chroma_client = get_chroma_client(str(request.app.state.chroma_dir))
    return search(query, course_id, db, chroma_client)


# ── Export ─────────────────────────────────────────────────────────────────


@router.get("/export/anki/{course_id}")
async def export_anki(request: Request, course_id: int) -> Response:
    from student.study_buddy.study.anki_exporter import export_deck

    db = request.app.state.db_paths["study_buddy"]

    with get_db(db) as conn:
        course = conn.execute("SELECT course_code FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    data = export_deck(course_id, db)
    filename = f"{course[0]}_flashcards.apkg"

    return Response(
        content=data,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Partials ───────────────────────────────────────────────────────────────


@router.get("/course-browser/partial", response_class=HTMLResponse)
async def course_browser_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["study_buddy"]
    with get_db(db) as conn:
        courses = [dict(r) for r in conn.execute(
            "SELECT * FROM courses ORDER BY semester DESC, course_code"
        ).fetchall()]
        for course in courses:
            course["doc_count"] = conn.execute(
                "SELECT COUNT(*) FROM documents WHERE course_id = ?", (course["id"],)
            ).fetchone()[0]
    return templates.TemplateResponse(
        "study_buddy/partials/course_browser.html",
        {"request": request, "courses": courses},
    )


@router.get("/document-uploader/partial", response_class=HTMLResponse)
async def document_uploader_partial(request: Request, course_id: int = 0) -> HTMLResponse:
    db = request.app.state.db_paths["study_buddy"]
    with get_db(db) as conn:
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE course_id = ? ORDER BY added_at DESC",
            (course_id,),
        ).fetchall()]
    return templates.TemplateResponse(
        "study_buddy/partials/document_uploader.html",
        {"request": request, "documents": docs, "course_id": course_id},
    )


@router.get("/qa-chat/partial", response_class=HTMLResponse)
async def qa_chat_partial(request: Request, answer_text: str = "", citations: str = "[]") -> HTMLResponse:
    try:
        parsed_citations = json.loads(citations)
    except json.JSONDecodeError:
        parsed_citations = []
    return templates.TemplateResponse(
        "study_buddy/partials/qa_chat.html",
        {"request": request, "answer": answer_text, "citations": parsed_citations},
    )


@router.get("/flashcard-review/partial", response_class=HTMLResponse)
async def flashcard_review_partial(request: Request, course_id: int = 0) -> HTMLResponse:
    db = request.app.state.db_paths["study_buddy"]
    now = datetime.now().isoformat()
    query = "SELECT * FROM flashcards WHERE (next_review IS NULL OR next_review <= ?)"
    params: list[Any] = [now]
    if course_id:
        query += " AND course_id = ?"
        params.append(course_id)
    query += " ORDER BY next_review ASC NULLS FIRST LIMIT 1"

    with get_db(db) as conn:
        row = conn.execute(query, params).fetchone()

    card = dict(row) if row else None
    return templates.TemplateResponse(
        "study_buddy/partials/flashcard_review.html",
        {"request": request, "card": card},
    )


@router.get("/search-results/partial", response_class=HTMLResponse)
async def search_results_partial(request: Request, query: str = "", course_id: int | None = None) -> HTMLResponse:
    results: list[dict] = []
    if query:
        from student.study_buddy.indexing.chroma_store import get_chroma_client
        from student.study_buddy.retrieval.search_engine import search

        db = request.app.state.db_paths["study_buddy"]
        chroma_client = get_chroma_client(str(request.app.state.chroma_dir))
        results = search(query, course_id, db, chroma_client)

    return templates.TemplateResponse(
        "study_buddy/partials/search_results.html",
        {"request": request, "results": results, "query": query},
    )


@router.get("/summary-viewer/partial", response_class=HTMLResponse)
async def summary_viewer_partial(request: Request, summary: str = "", detail_level: str = "") -> HTMLResponse:
    return templates.TemplateResponse(
        "study_buddy/partials/summary_viewer.html",
        {"request": request, "summary": summary, "detail_level": detail_level},
    )
