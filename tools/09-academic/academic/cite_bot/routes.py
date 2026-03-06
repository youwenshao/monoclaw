"""CiteBot FastAPI routes — citation formatting and bibliography management."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/cite-bot", tags=["CiteBot"])

templates = Jinja2Templates(directory="academic/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "cite-bot", **extra}


def _db(request: Request):
    return request.app.state.db_paths["cite_bot"]


def _mona_db(request: Request):
    return request.app.state.db_paths["mona_events"]


# ── Pydantic models ────────────────────────────────────────────────────────

class AddCitationRequest(BaseModel):
    doi: str | None = None
    title: str | None = None
    authors: str | None = None
    year: int | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    publisher: str | None = None
    url: str | None = None
    language: str = "en"
    entry_type: str = "article"
    raw_text: str | None = None


class FormatAllRequest(BaseModel):
    citation_ids: list[int]
    style: str = "apa7"


class ValidateDOIRequest(BaseModel):
    doi: str


class ProjectRequest(BaseModel):
    project_name: str
    default_style: str = "apa7"
    description: str | None = None


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def cite_bot_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
        verified = conn.execute(
            "SELECT COUNT(*) FROM citations WHERE verified = 1"
        ).fetchone()[0]
        projects = conn.execute(
            "SELECT COUNT(*) FROM bibliography_projects"
        ).fetchone()[0]
        duplicates_count = conn.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT doi FROM citations WHERE doi IS NOT NULL AND doi != '' "
            "  GROUP BY doi HAVING COUNT(*) > 1"
            ")"
        ).fetchone()[0]
        citations = [dict(r) for r in conn.execute(
            "SELECT * FROM citations ORDER BY created_at DESC"
        ).fetchall()]
        project_list = [dict(r) for r in conn.execute(
            "SELECT * FROM bibliography_projects ORDER BY created_at DESC"
        ).fetchall()]

    return templates.TemplateResponse(
        "cite_bot/index.html",
        _ctx(
            request,
            total=total,
            verified=verified,
            projects_count=projects,
            duplicates_count=duplicates_count,
            citations=citations,
            projects=project_list,
        ),
    )


# ── Citations CRUD ─────────────────────────────────────────────────────────

@router.post("/citations")
async def add_citation(request: Request, body: AddCitationRequest) -> dict[str, Any]:
    db = _db(request)

    if body.raw_text and not body.title:
        from academic.cite_bot.parsing.citation_parser import parse_raw_citation
        parsed = parse_raw_citation(body.raw_text)
        body = AddCitationRequest(**{**body.model_dump(), **parsed})

    if body.doi:
        from academic.cite_bot.validation.doi_checker import validate_doi
        doi_info = validate_doi(body.doi)
        if doi_info.get("valid") and doi_info.get("metadata"):
            meta = doi_info["metadata"]
            body = AddCitationRequest(**{
                **body.model_dump(),
                **{k: v for k, v in meta.items() if v and k in AddCitationRequest.model_fields},
            })

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO citations
               (doi, title, authors, year, journal, volume, issue, pages,
                publisher, url, language, entry_type, raw_text, verified)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (body.doi, body.title, body.authors, body.year, body.journal,
             body.volume, body.issue, body.pages, body.publisher, body.url,
             body.language, body.entry_type, body.raw_text, False),
        )
        citation_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Citation added: {body.title or body.doi or 'untitled'}",
    )

    return {"id": citation_id, "status": "created"}


@router.post("/import")
async def import_bibliography(request: Request, file: UploadFile) -> dict[str, Any]:
    db = _db(request)
    content = (await file.read()).decode("utf-8", errors="replace")
    filename = file.filename or ""

    if filename.endswith(".ris"):
        from academic.cite_bot.parsing.ris_parser import parse_ris
        entries = parse_ris(content)
    else:
        from academic.cite_bot.parsing.bibtex_parser import parse_bibtex
        entries = parse_bibtex(content)

    imported = 0
    with get_db(db) as conn:
        for entry in entries:
            conn.execute(
                """INSERT INTO citations
                   (doi, title, authors, year, journal, volume, issue, pages,
                    publisher, url, language, entry_type, raw_text, metadata_source, verified)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (entry.get("doi"), entry.get("title"), entry.get("authors"),
                 entry.get("year"), entry.get("journal"), entry.get("volume"),
                 entry.get("issue"), entry.get("pages"), entry.get("publisher"),
                 entry.get("url"), entry.get("language", "en"),
                 entry.get("entry_type", "article"), entry.get("raw_text"),
                 "bibtex" if not filename.endswith(".ris") else "ris", False),
            )
            imported += 1

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Imported {imported} citations from {filename}",
    )

    return {"imported": imported, "filename": filename}


@router.get("/citations")
async def list_citations(request: Request) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM citations ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/citations/{citation_id}")
async def get_citation(request: Request, citation_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM citations WHERE id = ?", (citation_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Citation not found")
    return dict(row)


@router.delete("/citations/{citation_id}")
async def delete_citation(request: Request, citation_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT title FROM citations WHERE id = ?", (citation_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Citation not found")
        conn.execute("DELETE FROM formatted_references WHERE citation_id = ?", (citation_id,))
        conn.execute("DELETE FROM project_citations WHERE citation_id = ?", (citation_id,))
        conn.execute("DELETE FROM citations WHERE id = ?", (citation_id,))

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Citation deleted: {row['title'] or citation_id}",
    )

    return {"status": "deleted", "id": citation_id}


# ── Formatting ─────────────────────────────────────────────────────────────

@router.get("/format/{citation_id}", response_class=HTMLResponse)
async def format_citation(request: Request, citation_id: int, style: str = "apa7") -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM citations WHERE id = ?", (citation_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Citation not found")

    citation = dict(row)

    from academic.cite_bot.formatting.style_registry import get_formatter
    formatter = get_formatter(style)
    formatted = formatter.format(citation)
    in_text_paren = formatter.in_text_parenthetical(citation)
    in_text_narrative = formatter.in_text_narrative(citation)

    with get_db(db) as conn:
        existing = conn.execute(
            "SELECT id FROM formatted_references WHERE citation_id = ? AND style = ?",
            (citation_id, style),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE formatted_references SET formatted_text = ?, generated_at = CURRENT_TIMESTAMP "
                "WHERE id = ?",
                (formatted, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO formatted_references (citation_id, style, formatted_text) VALUES (?,?,?)",
                (citation_id, style, formatted),
            )

    return templates.TemplateResponse(
        "cite_bot/partials/citation_preview.html",
        {
            "request": request,
            "citation": citation,
            "formatted": formatted,
            "style": style,
            "in_text_paren": in_text_paren,
            "in_text_narrative": in_text_narrative,
        },
    )


@router.post("/format-all")
async def format_all(request: Request, body: FormatAllRequest) -> dict[str, Any]:
    db = _db(request)
    results = []

    from academic.cite_bot.formatting.style_registry import get_formatter
    formatter = get_formatter(body.style)

    with get_db(db) as conn:
        for cid in body.citation_ids:
            row = conn.execute(
                "SELECT * FROM citations WHERE id = ?", (cid,)
            ).fetchone()
            if not row:
                results.append({"id": cid, "error": "not found"})
                continue

            citation = dict(row)
            formatted = formatter.format(citation)

            existing = conn.execute(
                "SELECT id FROM formatted_references WHERE citation_id = ? AND style = ?",
                (cid, body.style),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE formatted_references SET formatted_text = ?, generated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (formatted, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO formatted_references (citation_id, style, formatted_text) VALUES (?,?,?)",
                    (cid, body.style, formatted),
                )

            results.append({"id": cid, "formatted": formatted})

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Batch formatted {len(results)} citations in {body.style}",
    )

    return {"results": results, "style": body.style}


# ── Validation ─────────────────────────────────────────────────────────────

@router.post("/validate-doi")
async def validate_doi_endpoint(request: Request, body: ValidateDOIRequest) -> dict[str, Any]:
    from academic.cite_bot.validation.doi_checker import validate_doi
    result = validate_doi(body.doi)
    return result


# ── Duplicates ─────────────────────────────────────────────────────────────

@router.get("/duplicates")
async def find_duplicates(request: Request) -> list[dict]:
    db = _db(request)

    from academic.cite_bot.validation.duplicate_detector import detect_duplicates

    with get_db(db) as conn:
        all_citations = [dict(r) for r in conn.execute(
            "SELECT * FROM citations ORDER BY created_at DESC"
        ).fetchall()]

    groups = detect_duplicates(all_citations)
    return groups


# ── Export ─────────────────────────────────────────────────────────────────

@router.post("/export")
async def export_bibliography(request: Request, format: str = "bibtex") -> dict[str, Any]:
    db = _db(request)
    body = await request.json()
    project_id = body.get("project_id")
    citation_ids = body.get("citation_ids")

    with get_db(db) as conn:
        if project_id:
            rows = conn.execute(
                "SELECT c.* FROM citations c "
                "JOIN project_citations pc ON c.id = pc.citation_id "
                "WHERE pc.project_id = ? ORDER BY pc.sort_order",
                (project_id,),
            ).fetchall()
        elif citation_ids:
            placeholders = ",".join("?" * len(citation_ids))
            rows = conn.execute(
                f"SELECT * FROM citations WHERE id IN ({placeholders})",
                citation_ids,
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM citations ORDER BY created_at DESC").fetchall()

    citations = [dict(r) for r in rows]

    from academic.cite_bot.parsing.bibtex_parser import export_bibtex
    from academic.cite_bot.parsing.ris_parser import export_ris

    if format == "ris":
        output = export_ris(citations)
        content_type = "application/x-research-info-systems"
        ext = "ris"
    elif format == "plain":
        from academic.cite_bot.formatting.style_registry import get_formatter
        style = body.get("style", "apa7")
        formatter = get_formatter(style)
        lines = [formatter.format(c) for c in citations]
        output = "\n\n".join(lines)
        content_type = "text/plain"
        ext = "txt"
    else:
        output = export_bibtex(citations)
        content_type = "application/x-bibtex"
        ext = "bib"

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Exported {len(citations)} citations as {format}",
    )

    return {"content": output, "content_type": content_type, "filename": f"bibliography.{ext}"}


# ── Projects ───────────────────────────────────────────────────────────────

@router.get("/projects")
async def list_projects(request: Request) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM bibliography_projects ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/projects")
async def create_project(request: Request, body: ProjectRequest) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO bibliography_projects (project_name, default_style, description) VALUES (?,?,?)",
            (body.project_name, body.default_style, body.description),
        )
        project_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="cite-bot",
        summary=f"Project created: {body.project_name}",
    )

    return {"id": project_id, "status": "created"}


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/bibliography-table/partial", response_class=HTMLResponse)
async def bibliography_table_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        citations = [dict(r) for r in conn.execute(
            "SELECT c.*, fr.formatted_text, fr.style as formatted_style "
            "FROM citations c "
            "LEFT JOIN formatted_references fr ON c.id = fr.citation_id "
            "ORDER BY c.created_at DESC"
        ).fetchall()]
    return templates.TemplateResponse(
        "cite_bot/partials/bibliography_table.html",
        {"request": request, "citations": citations},
    )


@router.get("/export-panel/partial", response_class=HTMLResponse)
async def export_panel_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM bibliography_projects ORDER BY created_at DESC"
        ).fetchall()]
        total = conn.execute("SELECT COUNT(*) FROM citations").fetchone()[0]
    return templates.TemplateResponse(
        "cite_bot/partials/export_panel.html",
        {"request": request, "projects": projects, "total": total},
    )
