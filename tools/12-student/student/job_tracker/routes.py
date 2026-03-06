"""JobTracker FastAPI routes."""

from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/job-tracker", tags=["JobTracker"])

templates = Jinja2Templates(directory="student/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "job-tracker", **extra}


def _db(request: Request):
    return request.app.state.db_paths["job_tracker"]


def _events_db(request: Request):
    return request.app.state.db_paths["mona_events"]


def _uploads_dir(request: Request) -> Path:
    d: Path = request.app.state.workspace / "uploads" / "cv"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def job_tracker_page(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        total_apps = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        upcoming_interviews = conn.execute(
            "SELECT COUNT(*) FROM interviews WHERE datetime >= ?",
            (datetime.now().isoformat(),),
        ).fetchone()[0]
        offers = conn.execute(
            "SELECT COUNT(*) FROM applications WHERE stage IN ('offer','accepted')"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "job_tracker/index.html",
        _ctx(request, total_apps=total_apps, upcoming_interviews=upcoming_interviews, offers=offers),
    )


# ── Job Parsing ────────────────────────────────────────────────────────────


class ParseJobRequest(BaseModel):
    url: str = ""
    source: str = ""
    text: str = ""


@router.post("/jobs/parse")
async def parse_job(request: Request, body: ParseJobRequest) -> dict:
    if body.text:
        from student.job_tracker.parsing.generic_parser import parse_text
        return parse_text(body.text)

    if not body.url:
        raise HTTPException(status_code=400, detail="Provide a URL or paste text")

    from student.job_tracker.parsing.jd_structurer import detect_source
    source = body.source or detect_source(body.url)

    parsed: dict | None = None
    if source == "ctgoodjobs":
        from student.job_tracker.parsing.ctgoodjobs_parser import parse_ctgoodjobs
        parsed = await parse_ctgoodjobs(body.url)
    elif source == "jobsdb":
        from student.job_tracker.parsing.jobsdb_parser import parse_jobsdb
        parsed = await parse_jobsdb(body.url)
    elif source == "linkedin":
        from student.job_tracker.parsing.linkedin_parser import parse_linkedin
        parsed = await parse_linkedin(body.url)

    if parsed and parsed.get("description_raw"):
        from student.job_tracker.parsing.jd_structurer import structure_jd
        structured = await structure_jd(parsed["description_raw"], request.app.state.llm)
        for k, v in structured.items():
            if v and not parsed.get(k):
                parsed[k] = v
        return parsed

    if parsed:
        return parsed

    raise HTTPException(status_code=422, detail=f"Could not parse URL (source: {source}). Try pasting the job description text instead.")


# ── Jobs CRUD ──────────────────────────────────────────────────────────────


class AddJobRequest(BaseModel):
    source: str = "other"
    url: str = ""
    title: str
    company: str
    location: str = "Hong Kong"
    district: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    job_type: str = "full_time"
    industry: str = ""
    requirements: list[str] | None = None
    skills_required: list[str] | None = None
    benefits: str | None = None
    description_raw: str | None = None
    language: str = "en"
    posted_date: str | None = None
    deadline: str | None = None


@router.post("/jobs")
async def add_job(request: Request, body: AddJobRequest) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO job_listings
               (source, url, title, company, location, district,
                salary_min, salary_max, job_type, industry,
                requirements, skills_required, benefits, description_raw,
                language, posted_date, deadline)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body.source, body.url, body.title, body.company,
                body.location, body.district,
                body.salary_min, body.salary_max,
                body.job_type, body.industry,
                json.dumps(body.requirements or []),
                json.dumps(body.skills_required or []),
                body.benefits, body.description_raw,
                body.language, body.posted_date, body.deadline,
            ),
        )
        job_id = cursor.lastrowid

    emit_event(_events_db(request), event_type="action_completed", tool_name="job-tracker",
               summary=f"Job listing added: {body.title} at {body.company}")

    return {"job_id": job_id, "status": "created"}


@router.get("/jobs")
async def list_jobs(
    request: Request,
    source: str | None = None,
    industry: str | None = None,
    job_type: str | None = None,
) -> list[dict]:
    db = _db(request)
    query = "SELECT * FROM job_listings WHERE 1=1"
    params: list[Any] = []

    if source:
        query += " AND source = ?"
        params.append(source)
    if industry:
        query += " AND industry LIKE ?"
        params.append(f"%{industry}%")
    if job_type:
        query += " AND job_type = ?"
        params.append(job_type)

    query += " ORDER BY scraped_at DESC"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Job listing not found")

    job = dict(row)
    job["requirements"] = _safe_json(job.get("requirements"))
    job["skills_required"] = _safe_json(job.get("skills_required"))

    with get_db(db) as conn:
        cv_row = conn.execute(
            "SELECT * FROM cv_profiles ORDER BY last_updated DESC LIMIT 1"
        ).fetchone()

    if cv_row:
        cv = dict(cv_row)
        cv_skills = _safe_json(cv.get("skills")) or []
        jd_skills = job.get("skills_required") or []
        if isinstance(jd_skills, str):
            jd_skills = _safe_json(jd_skills) or []
        if isinstance(cv_skills, str):
            cv_skills = _safe_json(cv_skills) or []

        from student.job_tracker.matching.keyword_matcher import match_keywords
        match_result = match_keywords(cv_skills, jd_skills)
        job["match_score"] = match_result["match_score"]
        job["matched_skills"] = match_result["matched_skills"]
        job["unmatched_jd_skills"] = match_result["unmatched_jd_skills"]

    return job


# ── Applications ───────────────────────────────────────────────────────────


class CreateApplicationRequest(BaseModel):
    job_id: int
    cv_profile_id: int | None = None
    stage: str = "saved"
    notes: str = ""


@router.post("/applications")
async def create_application(request: Request, body: CreateApplicationRequest) -> dict:
    db = _db(request)

    match_score: float | None = None
    missing_kw: str | None = None

    if body.cv_profile_id:
        with get_db(db) as conn:
            cv_row = conn.execute("SELECT * FROM cv_profiles WHERE id = ?", (body.cv_profile_id,)).fetchone()
            job_row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (body.job_id,)).fetchone()

        if cv_row and job_row:
            cv_skills = _safe_json(dict(cv_row).get("skills")) or []
            jd_skills = _safe_json(dict(job_row).get("skills_required")) or []
            from student.job_tracker.matching.keyword_matcher import match_keywords
            result = match_keywords(cv_skills, jd_skills)
            match_score = result["match_score"]
            missing_kw = json.dumps(result["unmatched_jd_skills"])

    applied_date = datetime.now().strftime("%Y-%m-%d") if body.stage != "saved" else None

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO applications
               (job_id, cv_profile_id, match_score, missing_keywords, stage, applied_date, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (body.job_id, body.cv_profile_id, match_score, missing_kw, body.stage, applied_date, body.notes),
        )
        app_id = cursor.lastrowid

    emit_event(_events_db(request), event_type="action_completed", tool_name="job-tracker",
               summary=f"Application #{app_id} created (stage: {body.stage})")

    return {"application_id": app_id, "match_score": match_score, "status": "created"}


@router.get("/applications")
async def list_applications(request: Request) -> dict:
    from student.job_tracker.tracking.pipeline_manager import get_kanban_data
    return get_kanban_data(_db(request))


class UpdateStageRequest(BaseModel):
    stage: str


@router.put("/applications/{app_id}/stage")
async def update_application_stage(request: Request, app_id: int, body: UpdateStageRequest) -> dict:
    from student.job_tracker.tracking.pipeline_manager import update_stage
    try:
        update_stage(app_id, body.stage, _db(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    emit_event(_events_db(request), event_type="action_completed", tool_name="job-tracker",
               summary=f"Application #{app_id} moved to {body.stage}")

    return {"application_id": app_id, "stage": body.stage, "status": "updated"}


@router.get("/applications/{app_id}")
async def get_application(request: Request, app_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            """SELECT a.*, j.title, j.company, j.salary_min, j.salary_max,
                      j.job_type, j.skills_required as jd_skills, j.url as job_url
               FROM applications a
               LEFT JOIN job_listings j ON a.job_id = j.id
               WHERE a.id = ?""",
            (app_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Application not found")
    return dict(row)


# ── CV Upload & Matching ──────────────────────────────────────────────────


@router.post("/cv/upload")
async def upload_cv(request: Request, file: UploadFile) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".pdf", ".docx"):
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported")

    dest = _uploads_dir(request) / f"cv_{datetime.now().strftime('%Y%m%d_%H%M%S')}{suffix}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    from student.job_tracker.matching.cv_parser import parse_cv, extract_cv_data
    raw = parse_cv(str(dest))
    cv_data = await extract_cv_data(raw["text"], request.app.state.llm)

    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO cv_profiles (profile_name, skills, education, experience, keywords, file_path)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                file.filename,
                json.dumps(cv_data.get("skills", [])),
                json.dumps(cv_data.get("education", [])),
                json.dumps(cv_data.get("experience", [])),
                json.dumps(cv_data.get("keywords", [])),
                str(dest),
            ),
        )
        profile_id = cursor.lastrowid

    emit_event(_events_db(request), event_type="action_completed", tool_name="job-tracker",
               summary=f"CV uploaded and parsed: {file.filename}")

    return {"cv_profile_id": profile_id, "skills_found": len(cv_data.get("skills", [])), "status": "uploaded"}


@router.get("/cv/match/{job_id}")
async def cv_match(request: Request, job_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        job_row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
        cv_row = conn.execute("SELECT * FROM cv_profiles ORDER BY last_updated DESC LIMIT 1").fetchone()

    if not job_row:
        raise HTTPException(status_code=404, detail="Job listing not found")
    if not cv_row:
        raise HTTPException(status_code=404, detail="No CV profile found. Upload a CV first.")

    job = dict(job_row)
    cv = dict(cv_row)

    cv_skills = _safe_json(cv.get("skills")) or []
    jd_skills = _safe_json(job.get("skills_required")) or []

    from student.job_tracker.matching.keyword_matcher import match_keywords
    from student.job_tracker.matching.gap_analyzer import analyze_gaps

    match_result = match_keywords(cv_skills, jd_skills)
    gap_result = analyze_gaps(cv, job)

    return {
        "job_id": job_id,
        "cv_profile_id": cv["id"],
        "match_score": match_result["match_score"],
        "matched_skills": match_result["matched_skills"],
        "unmatched_jd_skills": match_result["unmatched_jd_skills"],
        "gap_analysis": gap_result,
    }


# ── Cover Letter Generation ───────────────────────────────────────────────


class CoverLetterRequest(BaseModel):
    job_id: int
    cv_profile_id: int


@router.post("/cover-letter/generate")
async def generate_cover_letter_route(request: Request, body: CoverLetterRequest) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        job_row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (body.job_id,)).fetchone()
        cv_row = conn.execute("SELECT * FROM cv_profiles WHERE id = ?", (body.cv_profile_id,)).fetchone()

    if not job_row:
        raise HTTPException(status_code=404, detail="Job listing not found")
    if not cv_row:
        raise HTTPException(status_code=404, detail="CV profile not found")

    from student.job_tracker.generation.cover_letter import generate_cover_letter
    letter = await generate_cover_letter(dict(job_row), dict(cv_row), request.app.state.llm)

    return {"cover_letter": letter, "job_id": body.job_id, "cv_profile_id": body.cv_profile_id}


# ── Interviews ─────────────────────────────────────────────────────────────


class ScheduleInterviewRequest(BaseModel):
    application_id: int
    interview_type: str
    datetime: str
    location: str = ""


@router.post("/interviews")
async def schedule_interview_route(request: Request, body: ScheduleInterviewRequest) -> dict:
    from student.job_tracker.tracking.interview_scheduler import schedule_interview
    try:
        iid = schedule_interview(body.application_id, body.interview_type, body.datetime, body.location, _db(request))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    emit_event(_events_db(request), event_type="action_completed", tool_name="job-tracker",
               summary=f"Interview scheduled (#{iid}) for application #{body.application_id}")

    return {"interview_id": iid, "status": "scheduled"}


@router.get("/interviews")
async def list_interviews(request: Request, days_ahead: int = 30) -> list[dict]:
    from student.job_tracker.tracking.interview_scheduler import get_upcoming_interviews
    return get_upcoming_interviews(_db(request), days_ahead)


# ── Analytics ──────────────────────────────────────────────────────────────


@router.get("/analytics")
async def analytics(request: Request) -> dict:
    from student.job_tracker.tracking.analytics_engine import (
        get_funnel_data, get_response_rate, get_weekly_volume, get_time_to_response,
    )
    db = _db(request)
    return {
        "funnel": get_funnel_data(db),
        "response_rate": get_response_rate(db),
        "weekly_volume": get_weekly_volume(db),
        "time_to_response": get_time_to_response(db),
    }


@router.post("/analytics/snapshot")
async def analytics_snapshot(request: Request) -> dict:
    from student.job_tracker.tracking.analytics_engine import create_snapshot
    create_snapshot(_db(request))
    return {"status": "snapshot_created"}


# ── Partials ──────────────────────────────────────────────────────────────


@router.get("/kanban-board/partial", response_class=HTMLResponse)
async def kanban_board_partial(request: Request) -> HTMLResponse:
    from student.job_tracker.tracking.pipeline_manager import get_kanban_data
    columns = get_kanban_data(_db(request))
    return templates.TemplateResponse(
        "job_tracker/partials/kanban_board.html",
        {"request": request, "columns": columns},
    )


@router.get("/job-detail/partial", response_class=HTMLResponse)
async def job_detail_partial(request: Request, job_id: int) -> HTMLResponse:
    job = await get_job(request, job_id)
    return templates.TemplateResponse(
        "job_tracker/partials/job_detail.html",
        {"request": request, "job": job},
    )


@router.get("/cover-letter-editor/partial", response_class=HTMLResponse)
async def cover_letter_editor_partial(request: Request, job_id: int, cv_profile_id: int) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        job_row = conn.execute("SELECT * FROM job_listings WHERE id = ?", (job_id,)).fetchone()
        cv_row = conn.execute("SELECT * FROM cv_profiles WHERE id = ?", (cv_profile_id,)).fetchone()

    job = dict(job_row) if job_row else {}
    cv = dict(cv_row) if cv_row else {}

    from student.job_tracker.generation.cover_letter import generate_cover_letter
    letter = await generate_cover_letter(job, cv, request.app.state.llm)

    return templates.TemplateResponse(
        "job_tracker/partials/cover_letter_editor.html",
        {"request": request, "cover_letter": letter, "job": job},
    )


@router.get("/analytics-charts/partial", response_class=HTMLResponse)
async def analytics_charts_partial(request: Request) -> HTMLResponse:
    from student.job_tracker.tracking.analytics_engine import (
        get_funnel_data, get_response_rate, get_weekly_volume,
    )
    db = _db(request)
    funnel = get_funnel_data(db)
    response_rate = get_response_rate(db)
    weekly = get_weekly_volume(db)

    return templates.TemplateResponse(
        "job_tracker/partials/analytics_charts.html",
        {"request": request, "funnel": funnel, "response_rate": response_rate, "weekly": weekly},
    )


@router.get("/interview-calendar/partial", response_class=HTMLResponse)
async def interview_calendar_partial(request: Request) -> HTMLResponse:
    from student.job_tracker.tracking.interview_scheduler import get_upcoming_interviews
    interviews = get_upcoming_interviews(_db(request))
    return templates.TemplateResponse(
        "job_tracker/partials/interview_calendar.html",
        {"request": request, "interviews": interviews},
    )


# ── Helpers ────────────────────────────────────────────────────────────────


def _safe_json(val):
    if isinstance(val, str):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return val
    return val
