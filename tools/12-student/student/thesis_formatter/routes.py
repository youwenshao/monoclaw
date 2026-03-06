"""ThesisFormatter FastAPI routes."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/thesis-formatter", tags=["ThesisFormatter"])

templates = Jinja2Templates(directory="student/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "thesis-formatter", **extra}


def _output_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "thesis_files"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def thesis_formatter_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        profiles_count = conn.execute("SELECT COUNT(*) FROM formatting_profiles").fetchone()[0]
        projects_count = conn.execute("SELECT COUNT(*) FROM thesis_projects").fetchone()[0]
        issues_count = conn.execute(
            "SELECT COUNT(*) FROM validation_results WHERE passed = 0"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "thesis_formatter/index.html",
        _ctx(request, profiles_count=profiles_count, projects_count=projects_count, issues_count=issues_count),
    )


# ── Profiles ───────────────────────────────────────────────────────────────

@router.get("/profiles")
async def list_profiles(request: Request) -> list[dict]:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM formatting_profiles ORDER BY university").fetchall()
    return [dict(r) for r in rows]


@router.get("/profiles/{profile_id}")
async def get_profile(request: Request, profile_id: int) -> dict:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (profile_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return dict(row)


# ── Projects ───────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    title: str
    author: str
    university: str
    department: str
    degree: str
    supervisor: str
    year: int
    profile_id: int


@router.post("/projects")
async def create_project(request: Request, body: CreateProjectRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        profile = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (body.profile_id,)).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO thesis_projects
               (title, author, university, department, degree, supervisor, year, profile_id)
               VALUES (?,?,?,?,?,?,?,?)""",
            (body.title, body.author, body.university, body.department,
             body.degree, body.supervisor, body.year, body.profile_id),
        )
        project_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="thesis-formatter",
        summary=f"Thesis project '{body.title}' created for {body.university}",
    )

    return {"project_id": project_id, "status": "created"}


@router.get("/projects")
async def list_projects(request: Request) -> list[dict]:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT p.*, f.university as profile_university FROM thesis_projects p "
            "LEFT JOIN formatting_profiles f ON p.profile_id = f.id "
            "ORDER BY p.created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/projects/{project_id}/upload")
async def upload_thesis(request: Request, project_id: int, file: UploadFile) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are accepted")

    output_dir = _output_dir(request)
    dest = output_dir / f"project_{project_id}_{file.filename}"
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with get_db(db) as conn:
        conn.execute(
            "UPDATE thesis_projects SET source_file = ? WHERE id = ?",
            (str(dest), project_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="thesis-formatter",
        summary=f"Thesis file uploaded for project #{project_id}",
    )

    return {"project_id": project_id, "file_path": str(dest), "status": "uploaded"}


@router.post("/projects/{project_id}/validate")
async def validate_thesis(request: Request, project_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    if not project.get("source_file") or not Path(project["source_file"]).exists():
        raise HTTPException(status_code=400, detail="No thesis file uploaded")

    with get_db(db) as conn:
        profile = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (project["profile_id"],)).fetchone()
    if not profile:
        raise HTTPException(status_code=404, detail="Formatting profile not found")

    profile_dict = dict(profile)

    from student.thesis_formatter.validation.format_checker import check_format
    from student.thesis_formatter.validation.completeness_checker import check_completeness
    from student.thesis_formatter.validation.report_generator import generate_report

    format_checks = check_format(project["source_file"], profile_dict)
    completeness_checks = check_completeness(project["source_file"], profile_dict)
    all_checks = format_checks + completeness_checks
    report = generate_report(all_checks)

    with get_db(db) as conn:
        conn.execute("DELETE FROM validation_results WHERE project_id = ?", (project_id,))
        for check in all_checks:
            conn.execute(
                """INSERT INTO validation_results
                   (project_id, check_type, passed, message, location, severity)
                   VALUES (?,?,?,?,?,?)""",
                (project_id, check["check_type"], check["passed"],
                 check["message"], check["location"], check["severity"]),
            )
        status = "passed" if report["failed"] == 0 else "issues_found"
        conn.execute(
            "UPDATE thesis_projects SET validation_status = ? WHERE id = ?",
            (status, project_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="thesis-formatter",
        summary=f"Validation for project #{project_id}: {report['passed']}/{report['total']} checks passed",
    )

    return {"project_id": project_id, "report": report}


@router.get("/projects/{project_id}/validation")
async def get_validation_results(request: Request, project_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM validation_results WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()
    checks = [dict(r) for r in rows]

    from student.thesis_formatter.validation.report_generator import generate_report
    report = generate_report(checks)
    return {"project_id": project_id, "report": report}


@router.post("/projects/{project_id}/format")
async def format_thesis(request: Request, project_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    if not project.get("source_file") or not Path(project["source_file"]).exists():
        raise HTTPException(status_code=400, detail="No thesis file uploaded")

    with get_db(db) as conn:
        profile = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (project["profile_id"],)).fetchone()
    profile_dict = dict(profile)

    from student.thesis_formatter.formatting.template_engine import apply_template
    from student.thesis_formatter.formatting.page_numbering import apply_page_numbering

    formatted_path = apply_template(project["source_file"], profile_dict)
    formatted_path = apply_page_numbering(formatted_path)

    with get_db(db) as conn:
        conn.execute(
            "UPDATE thesis_projects SET formatted_file = ? WHERE id = ?",
            (formatted_path, project_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="thesis-formatter",
        summary=f"Formatting applied to project #{project_id}",
    )

    return {"project_id": project_id, "formatted_file": formatted_path, "status": "formatted"}


@router.post("/projects/{project_id}/toc")
async def generate_toc_route(request: Request, project_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    source = project.get("formatted_file") or project.get("source_file")
    if not source or not Path(source).exists():
        raise HTTPException(status_code=400, detail="No thesis file available")

    from student.thesis_formatter.generation.toc_generator import generate_toc
    output = generate_toc(source)

    with get_db(db) as conn:
        conn.execute("UPDATE thesis_projects SET formatted_file = ? WHERE id = ?", (output, project_id))

    return {"project_id": project_id, "file": output, "status": "toc_generated"}


@router.post("/projects/{project_id}/bibliography")
async def format_bibliography_route(request: Request, project_id: int, file: UploadFile) -> dict[str, Any]:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    source = project.get("formatted_file") or project.get("source_file")
    if not source or not Path(source).exists():
        raise HTTPException(status_code=400, detail="No thesis file available")

    if not file.filename or not file.filename.endswith(".bib"):
        raise HTTPException(status_code=400, detail="Only .bib files are accepted")

    output_dir = _output_dir(request)
    bib_path = output_dir / f"project_{project_id}_{file.filename}"
    with open(bib_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    with get_db(db) as conn:
        profile = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (project["profile_id"],)).fetchone()

    citation_style = "apa"
    if profile:
        profile_dict = dict(profile)
        citation_style = profile_dict.get("notes", "")
        if "apa" in citation_style.lower():
            citation_style = "apa"
        elif "mla" in citation_style.lower():
            citation_style = "mla"
        elif "ieee" in citation_style.lower():
            citation_style = "ieee"
        else:
            citation_style = "apa"

    from student.thesis_formatter.bibliography.bibtex_handler import parse_bibtex
    from student.thesis_formatter.bibliography.citation_inserter import insert_citations

    references = parse_bibtex(str(bib_path))
    output = insert_citations(source, references, citation_style)

    with get_db(db) as conn:
        conn.execute("UPDATE thesis_projects SET formatted_file = ? WHERE id = ?", (output, project_id))

    return {"project_id": project_id, "references_count": len(references), "file": output, "status": "bibliography_formatted"}


@router.get("/projects/{project_id}/export/docx")
async def export_docx(request: Request, project_id: int) -> FileResponse:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    file_path = project.get("formatted_file") or project.get("source_file")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=404, detail="No file available for download")

    return FileResponse(
        path=file_path,
        filename=f"{project['title']}.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@router.get("/projects/{project_id}/export/pdf")
async def export_pdf(request: Request, project_id: int) -> FileResponse:
    db = request.app.state.db_paths["thesis_formatter"]

    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project = dict(project)
    source = project.get("formatted_file") or project.get("source_file")
    if not source or not Path(source).exists():
        raise HTTPException(status_code=404, detail="No file available for conversion")

    try:
        from docx2pdf import convert
        pdf_path = Path(source).with_suffix(".pdf")
        convert(source, str(pdf_path))
    except ImportError:
        raise HTTPException(status_code=501, detail="PDF conversion not available (docx2pdf not installed)")

    return FileResponse(
        path=str(pdf_path),
        filename=f"{project['title']}.pdf",
        media_type="application/pdf",
    )


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/template-selector/partial", response_class=HTMLResponse)
async def template_selector_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        profiles = [dict(r) for r in conn.execute("SELECT * FROM formatting_profiles ORDER BY university").fetchall()]
    return templates.TemplateResponse(
        "thesis_formatter/partials/template_selector.html",
        {"request": request, "profiles": profiles},
    )


@router.get("/validation-report/partial", response_class=HTMLResponse)
async def validation_report_partial(request: Request, project_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        results = [dict(r) for r in conn.execute(
            "SELECT * FROM validation_results WHERE project_id = ? ORDER BY id",
            (project_id,),
        ).fetchall()]

    from student.thesis_formatter.validation.report_generator import generate_report
    report = generate_report(results)

    return templates.TemplateResponse(
        "thesis_formatter/partials/validation_report.html",
        {"request": request, "report": report, "project_id": project_id},
    )


@router.get("/format-preview/partial", response_class=HTMLResponse)
async def format_preview_partial(request: Request, project_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        project = conn.execute("SELECT * FROM thesis_projects WHERE id = ?", (project_id,)).fetchone()
        profile = None
        if project:
            profile = conn.execute("SELECT * FROM formatting_profiles WHERE id = ?", (dict(project)["profile_id"],)).fetchone()

    return templates.TemplateResponse(
        "thesis_formatter/partials/format_preview.html",
        {"request": request, "project": dict(project) if project else {}, "profile": dict(profile) if profile else {}},
    )


@router.get("/section-editor/partial", response_class=HTMLResponse)
async def section_editor_partial(request: Request, project_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["thesis_formatter"]
    with get_db(db) as conn:
        sections = [dict(r) for r in conn.execute(
            "SELECT * FROM sections WHERE project_id = ? ORDER BY page_start",
            (project_id,),
        ).fetchall()]

    return templates.TemplateResponse(
        "thesis_formatter/partials/section_editor.html",
        {"request": request, "sections": sections, "project_id": project_id},
    )
