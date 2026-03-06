"""DocuWriter FastAPI routes."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["DocuWriter"])


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "docu-writer",
        **extra,
    }


# ── Page ───────────────────────────────────────────────────────────────────


@router.get("/docu-writer/", response_class=HTMLResponse)
async def docu_writer_page(request: Request) -> HTMLResponse:
    db_path = request.app.state.db_paths["docu_writer"]

    with get_db(db_path) as conn:
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM projects ORDER BY last_analyzed DESC"
        ).fetchall()]
        recent_docs = [dict(r) for r in conn.execute(
            "SELECT * FROM generated_docs ORDER BY generated_at DESC LIMIT 10"
        ).fetchall()]

    return templates.TemplateResponse(
        "docu_writer/index.html",
        _ctx(request, projects=projects, recent_docs=recent_docs),
    )


# ── Analyze project ───────────────────────────────────────────────────────


@router.post("/api/docu-writer/analyze")
async def analyze_project(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    path = Path(project_path).expanduser().resolve()
    if not path.is_dir():
        raise HTTPException(status_code=404, detail=f"Directory not found: {path}")

    from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectAnalyzer

    analyzer = ProjectAnalyzer()
    info = analyzer.analyze(path)

    db_path = request.app.state.db_paths["docu_writer"]
    with get_db(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM projects WHERE project_path = ?", (info.project_path,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE projects SET project_name=?, primary_language=?,
                   last_analyzed=CURRENT_TIMESTAMP, file_count=?,
                   total_functions=?, documented_functions=?,
                   documentation_coverage=? WHERE id=?""",
                (
                    info.project_name,
                    info.primary_language,
                    info.file_count,
                    info.total_functions,
                    info.documented_functions,
                    info.documentation_coverage,
                    existing["id"],
                ),
            )
            project_id = existing["id"]
        else:
            cursor = conn.execute(
                """INSERT INTO projects
                   (project_path, project_name, primary_language, last_analyzed,
                    file_count, total_functions, documented_functions, documentation_coverage)
                   VALUES (?,?,?,CURRENT_TIMESTAMP,?,?,?,?)""",
                (
                    info.project_path,
                    info.project_name,
                    info.primary_language,
                    info.file_count,
                    info.total_functions,
                    info.documented_functions,
                    info.documentation_coverage,
                ),
            )
            project_id = cursor.lastrowid

        conn.execute("DELETE FROM code_elements WHERE project_id = ?", (project_id,))
        for elem in info.code_elements:
            conn.execute(
                """INSERT INTO code_elements
                   (project_id, file_path, element_type, element_name,
                    signature, has_docstring, docstring, line_number)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    project_id,
                    elem.file_path,
                    elem.element_type,
                    elem.element_name,
                    elem.signature,
                    elem.has_docstring,
                    elem.docstring,
                    elem.line_number,
                ),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"Analyzed {info.project_name}: {info.file_count} files, {info.total_functions} functions",
    )

    return {
        "project_id": project_id,
        "project_name": info.project_name,
        "primary_language": info.primary_language,
        "file_count": info.file_count,
        "total_functions": info.total_functions,
        "documented_functions": info.documented_functions,
        "documentation_coverage": info.documentation_coverage,
        "language_breakdown": info.language_breakdown,
    }


# ── Generate README ───────────────────────────────────────────────────────


@router.post("/api/docu-writer/readme")
async def generate_readme(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectAnalyzer
    from vibe_coder.docu_writer.generators.readme_generator import ReadmeGenerator

    analyzer = ProjectAnalyzer()
    info = analyzer.analyze(Path(project_path).expanduser().resolve())
    llm = request.app.state.llm

    generator = ReadmeGenerator()
    content = await generator.generate(info, llm)

    project_id = _upsert_project(request, info)
    _save_doc(request, project_id, "readme", content, body.get("output_path"))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"README generated for {info.project_name}",
    )

    return {"content": content, "project_name": info.project_name}


# ── Generate API docs ─────────────────────────────────────────────────────


@router.post("/api/docu-writer/api-docs")
async def generate_api_docs(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectAnalyzer
    from vibe_coder.docu_writer.generators.api_doc_generator import ApiDocGenerator

    analyzer = ProjectAnalyzer()
    info = analyzer.analyze(Path(project_path).expanduser().resolve())
    llm = request.app.state.llm

    generator = ApiDocGenerator()
    content = await generator.generate(info.code_elements, info.project_name, llm)

    project_id = _upsert_project(request, info)
    _save_doc(request, project_id, "api_reference", content, body.get("output_path"))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"API docs generated for {info.project_name} ({len(info.code_elements)} elements)",
    )

    return {"content": content, "project_name": info.project_name}


# ── Generate docstrings ───────────────────────────────────────────────────


@router.post("/api/docu-writer/docstrings")
async def generate_docstrings(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectAnalyzer
    from vibe_coder.docu_writer.generators.docstring_generator import DocstringGenerator

    analyzer = ProjectAnalyzer()
    info = analyzer.analyze(Path(project_path).expanduser().resolve())
    llm = request.app.state.llm

    style = body.get("style", "google")
    generator = DocstringGenerator()
    results = await generator.generate(info.code_elements, llm, style=style)

    project_id = _upsert_project(request, info)
    _save_doc(
        request,
        project_id,
        "docstrings",
        json.dumps([asdict(r) for r in results], indent=2),
        body.get("output_path"),
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"Generated {len(results)} docstrings for {info.project_name}",
    )

    return {
        "docstrings": [asdict(r) for r in results],
        "count": len(results),
        "project_name": info.project_name,
    }


# ── Generate architecture ─────────────────────────────────────────────────


@router.post("/api/docu-writer/architecture")
async def generate_architecture(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    from vibe_coder.docu_writer.analyzers.project_analyzer import ProjectAnalyzer
    from vibe_coder.docu_writer.generators.architecture_generator import ArchitectureGenerator

    analyzer = ProjectAnalyzer()
    info = analyzer.analyze(Path(project_path).expanduser().resolve())
    llm = request.app.state.llm

    generator = ArchitectureGenerator()
    content = await generator.generate(info, info.code_elements, llm)

    project_id = _upsert_project(request, info)
    _save_doc(request, project_id, "architecture", content, body.get("output_path"))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"Architecture doc generated for {info.project_name}",
    )

    return {"content": content, "project_name": info.project_name}


# ── Generate changelog ─────────────────────────────────────────────────────


@router.post("/api/docu-writer/changelog")
async def generate_changelog(request: Request) -> dict[str, Any]:
    body = await request.json()
    repo_path = body.get("repo_path") or body.get("project_path")
    if not repo_path:
        raise HTTPException(status_code=400, detail="repo_path is required")

    from vibe_coder.docu_writer.analyzers.git_analyzer import GitAnalyzer
    from vibe_coder.docu_writer.generators.changelog_generator import ChangelogGenerator

    git_analyzer = GitAnalyzer()
    from_tag = body.get("from_tag")
    to_tag = body.get("to_tag")
    version = body.get("version")

    if from_tag and to_tag:
        commits = git_analyzer.get_commits_between_tags(repo_path, from_tag, to_tag)
    else:
        limit = body.get("limit", 50)
        commits = git_analyzer.get_commits(repo_path, limit=limit)

    llm = request.app.state.llm
    generator = ChangelogGenerator()
    content = await generator.generate(commits, llm, version=version)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="docu-writer",
        summary=f"Changelog generated from {len(commits)} commits",
    )

    return {"content": content, "commit_count": len(commits)}


# ── Check freshness ───────────────────────────────────────────────────────


@router.post("/api/docu-writer/freshness")
async def check_freshness(request: Request) -> dict[str, Any]:
    body = await request.json()
    project_path = body.get("project_path")
    if not project_path:
        raise HTTPException(status_code=400, detail="project_path is required")

    from vibe_coder.docu_writer.analyzers.freshness_checker import FreshnessChecker

    checker = FreshnessChecker()
    db_path = request.app.state.db_paths["docu_writer"]
    report = checker.check(Path(project_path).expanduser().resolve(), db_path)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="info",
        tool_name="docu-writer",
        summary=f"Freshness check: {report.freshness_ratio:.0%} fresh ({report.stale_count} stale)",
    )

    return {
        "total_checked": report.total_checked,
        "stale_count": report.stale_count,
        "fresh_count": report.fresh_count,
        "freshness_ratio": report.freshness_ratio,
        "stale_files": report.stale_files,
        "stale_functions": [asdict(s) for s in report.stale_functions],
    }


# ── List projects ─────────────────────────────────────────────────────────


@router.get("/api/docu-writer/projects")
async def list_projects(request: Request) -> list[dict[str, Any]]:
    db_path = request.app.state.db_paths["docu_writer"]
    with get_db(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM projects ORDER BY last_analyzed DESC"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Helpers ───────────────────────────────────────────────────────────────


def _upsert_project(request: Request, info) -> int:
    """Ensure a project row exists and return its id."""
    db_path = request.app.state.db_paths["docu_writer"]
    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM projects WHERE project_path = ?", (info.project_path,)
        ).fetchone()
        if row:
            conn.execute(
                """UPDATE projects SET project_name=?, primary_language=?,
                   last_analyzed=CURRENT_TIMESTAMP, file_count=?,
                   total_functions=?, documented_functions=?,
                   documentation_coverage=? WHERE id=?""",
                (
                    info.project_name,
                    info.primary_language,
                    info.file_count,
                    info.total_functions,
                    info.documented_functions,
                    info.documentation_coverage,
                    row["id"],
                ),
            )
            return row["id"]

        cursor = conn.execute(
            """INSERT INTO projects
               (project_path, project_name, primary_language, last_analyzed,
                file_count, total_functions, documented_functions, documentation_coverage)
               VALUES (?,?,?,CURRENT_TIMESTAMP,?,?,?,?)""",
            (
                info.project_path,
                info.project_name,
                info.primary_language,
                info.file_count,
                info.total_functions,
                info.documented_functions,
                info.documentation_coverage,
            ),
        )
        return cursor.lastrowid  # type: ignore[return-value]


def _save_doc(
    request: Request,
    project_id: int,
    doc_type: str,
    content: str,
    output_path: str | None = None,
) -> None:
    """Persist a generated document to the database."""
    db_path = request.app.state.db_paths["docu_writer"]
    llm_name = getattr(request.app.state.llm, "model_name", "unknown")
    params = json.dumps({"model": llm_name})

    with get_db(db_path) as conn:
        conn.execute(
            """INSERT INTO generated_docs
               (project_id, doc_type, content, output_path, generation_params)
               VALUES (?,?,?,?,?)""",
            (project_id, doc_type, content, output_path, params),
        )
