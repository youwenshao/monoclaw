"""TranslateAssist FastAPI routes — academic Chinese-English translation."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/translate-assist", tags=["TranslateAssist"])

templates = Jinja2Templates(directory="academic/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "translate-assist", **extra}


def _db(request: Request):
    return request.app.state.db_paths["translate_assist"]


def _mona_db(request: Request):
    return request.app.state.db_paths["mona_events"]


# ── Pydantic models ────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    project_name: str
    source_language: str = "en"
    target_language: str = "tc"
    domain: str = "general"
    source_file: str | None = None


class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "tc"
    domain: str = "general"


class ConvertRequest(BaseModel):
    text: str
    target: str  # "tc" or "sc"


class AddGlossaryTermRequest(BaseModel):
    term_en: str | None = None
    term_tc: str | None = None
    term_sc: str | None = None
    domain: str | None = None
    definition: str | None = None
    source: str | None = None


class UpdateGlossaryTermRequest(BaseModel):
    term_en: str | None = None
    term_tc: str | None = None
    term_sc: str | None = None
    domain: str | None = None
    definition: str | None = None
    source: str | None = None


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def translate_assist_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        projects_count = conn.execute(
            "SELECT COUNT(*) FROM translation_projects"
        ).fetchone()[0]
        segments_translated = conn.execute(
            "SELECT COUNT(*) FROM translation_segments WHERE translated_text IS NOT NULL AND translated_text != ''"
        ).fetchone()[0]
        glossary_count = conn.execute(
            "SELECT COUNT(*) FROM glossary_terms"
        ).fetchone()[0]
        memory_count = conn.execute(
            "SELECT COUNT(*) FROM translation_memory"
        ).fetchone()[0]
        projects = [dict(r) for r in conn.execute(
            "SELECT * FROM translation_projects ORDER BY created_at DESC"
        ).fetchall()]
        glossary_domains = [r[0] for r in conn.execute(
            "SELECT DISTINCT domain FROM glossary_terms WHERE domain IS NOT NULL ORDER BY domain"
        ).fetchall()]

    return templates.TemplateResponse(
        "translate_assist/index.html",
        _ctx(
            request,
            projects_count=projects_count,
            segments_translated=segments_translated,
            glossary_count=glossary_count,
            memory_count=memory_count,
            projects=projects,
            glossary_domains=glossary_domains,
        ),
    )


# ── Projects CRUD ──────────────────────────────────────────────────────────

@router.post("/projects")
async def create_project(request: Request, body: CreateProjectRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO translation_projects
               (project_name, source_language, target_language, domain, source_file, status)
               VALUES (?,?,?,?,?,?)""",
            (body.project_name, body.source_language, body.target_language,
             body.domain, body.source_file, "in_progress"),
        )
        project_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="translate-assist",
        summary=f"Translation project created: {body.project_name}",
    )

    return {"id": project_id, "status": "created"}


@router.get("/projects")
async def list_projects(request: Request) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM translation_projects ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/projects/{project_id}")
async def get_project(request: Request, project_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM translation_projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Project not found")
        project = dict(row)

        segments = [dict(r) for r in conn.execute(
            "SELECT * FROM translation_segments WHERE project_id = ? ORDER BY segment_index",
            (project_id,),
        ).fetchall()]

    return {**project, "segments": segments}


# ── Translation ────────────────────────────────────────────────────────────

@router.post("/translate")
async def translate_text(request: Request, body: TranslateRequest) -> dict[str, Any]:
    db = _db(request)

    from academic.translate_assist.translation.translator import translate
    from academic.translate_assist.terminology.term_enforcer import enforce_glossary

    with get_db(db) as conn:
        glossary = [dict(r) for r in conn.execute(
            "SELECT * FROM glossary_terms WHERE domain = ? OR domain IS NULL",
            (body.domain,),
        ).fetchall()]

    result = translate(
        body.text,
        source_lang=body.source_lang,
        target_lang=body.target_lang,
        domain=body.domain,
        llm=request.app.state.llm,
    )

    enforced = enforce_glossary(result["translated"], glossary, body.target_lang)

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO translation_memory
               (source_text, source_language, translated_text, target_language, domain, quality_score)
               VALUES (?,?,?,?,?,?)""",
            (body.text, body.source_lang, enforced["text"], body.target_lang,
             body.domain, result.get("confidence", 0.0)),
        )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="translate-assist",
        summary=f"Translated {len(body.text)} chars ({body.source_lang}→{body.target_lang})",
    )

    return {
        "translated": enforced["text"],
        "confidence": result.get("confidence", 0.0),
        "terms_enforced": enforced.get("terms_applied", []),
        "source_lang": body.source_lang,
        "target_lang": body.target_lang,
    }


@router.post("/translate-document")
async def translate_document(request: Request, file: UploadFile) -> dict[str, Any]:
    db = _db(request)
    content = await file.read()
    filename = file.filename or "document"

    from academic.translate_assist.processing.document_parser import parse_document
    from academic.translate_assist.processing.segmenter import segment_text
    from academic.translate_assist.translation.translator import translate

    parsed = parse_document(content, filename)
    segments = segment_text(parsed["text"])

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO translation_projects
               (project_name, source_language, target_language, domain, source_file, status)
               VALUES (?,?,?,?,?,?)""",
            (filename, "en", "tc", "general", filename, "in_progress"),
        )
        project_id = cursor.lastrowid

        for idx, seg in enumerate(segments):
            result = translate(
                seg["text"],
                source_lang="en",
                target_lang="tc",
                domain="general",
                llm=request.app.state.llm,
            )
            conn.execute(
                """INSERT INTO translation_segments
                   (project_id, segment_index, section_name, source_text, translated_text,
                    review_status, confidence)
                   VALUES (?,?,?,?,?,?,?)""",
                (project_id, idx, seg.get("section", ""),
                 seg["text"], result["translated"], "auto",
                 result.get("confidence", 0.0)),
            )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="translate-assist",
        summary=f"Document translated: {filename} ({len(segments)} segments)",
    )

    return {
        "project_id": project_id,
        "filename": filename,
        "segments": len(segments),
        "status": "in_progress",
    }


# ── Glossary CRUD ──────────────────────────────────────────────────────────

@router.get("/glossary")
async def list_glossary(request: Request, domain: str | None = None) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        if domain:
            rows = conn.execute(
                "SELECT * FROM glossary_terms WHERE domain = ? ORDER BY term_en",
                (domain,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM glossary_terms ORDER BY term_en"
            ).fetchall()
    return [dict(r) for r in rows]


@router.post("/glossary")
async def add_glossary_term(request: Request, body: AddGlossaryTermRequest) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO glossary_terms
               (term_en, term_tc, term_sc, domain, definition, source)
               VALUES (?,?,?,?,?,?)""",
            (body.term_en, body.term_tc, body.term_sc, body.domain,
             body.definition, body.source),
        )
        term_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="translate-assist",
        summary=f"Glossary term added: {body.term_en or body.term_tc or 'term'}",
    )

    return {"id": term_id, "status": "created"}


@router.put("/glossary/{term_id}")
async def update_glossary_term(request: Request, term_id: int, body: UpdateGlossaryTermRequest) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        existing = conn.execute(
            "SELECT * FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Term not found")

        updates = {k: v for k, v in body.model_dump().items() if v is not None}
        if updates:
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE glossary_terms SET {set_clause} WHERE id = ?",
                (*updates.values(), term_id),
            )

    return {"id": term_id, "status": "updated"}


@router.delete("/glossary/{term_id}")
async def delete_glossary_term(request: Request, term_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT term_en FROM glossary_terms WHERE id = ?", (term_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Term not found")
        conn.execute("DELETE FROM glossary_terms WHERE id = ?", (term_id,))

    return {"status": "deleted", "id": term_id}


# ── TC/SC Conversion ──────────────────────────────────────────────────────

@router.post("/convert")
async def convert_chinese(request: Request, body: ConvertRequest) -> dict[str, Any]:
    from academic.translate_assist.processing.chinese_converter import convert

    result = convert(body.text, target=body.target)
    return {"converted": result, "target": body.target}


# ── Translation Memory ────────────────────────────────────────────────────

@router.get("/memory")
async def search_translation_memory(request: Request, q: str = "") -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        if q:
            rows = conn.execute(
                "SELECT * FROM translation_memory "
                "WHERE source_text LIKE ? OR translated_text LIKE ? "
                "ORDER BY quality_score DESC LIMIT 50",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM translation_memory ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
    return [dict(r) for r in rows]


# ── Export ─────────────────────────────────────────────────────────────────

@router.post("/export/{project_id}")
async def export_translated_document(request: Request, project_id: int) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        project_row = conn.execute(
            "SELECT * FROM translation_projects WHERE id = ?", (project_id,)
        ).fetchone()
        if not project_row:
            raise HTTPException(status_code=404, detail="Project not found")

        segments = [dict(r) for r in conn.execute(
            "SELECT * FROM translation_segments WHERE project_id = ? ORDER BY segment_index",
            (project_id,),
        ).fetchall()]

    project = dict(project_row)

    translated_parts = []
    for seg in segments:
        section = seg.get("section_name", "")
        text = seg.get("translated_text", "")
        if section:
            translated_parts.append(f"\n## {section}\n")
        translated_parts.append(text)

    full_text = "\n\n".join(translated_parts)

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="translate-assist",
        summary=f"Exported translated document: {project['project_name']}",
    )

    return {
        "project_id": project_id,
        "project_name": project["project_name"],
        "content": full_text,
        "segments": len(segments),
    }


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/editor/partial", response_class=HTMLResponse)
async def editor_partial(request: Request, project_id: int) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        project = dict(conn.execute(
            "SELECT * FROM translation_projects WHERE id = ?", (project_id,)
        ).fetchone() or {})
        segments = [dict(r) for r in conn.execute(
            "SELECT * FROM translation_segments WHERE project_id = ? ORDER BY segment_index",
            (project_id,),
        ).fetchall()]
    return templates.TemplateResponse(
        "translate_assist/partials/editor.html",
        {"request": request, "project": project, "segments": segments},
    )


@router.get("/glossary-panel/partial", response_class=HTMLResponse)
async def glossary_panel_partial(request: Request, domain: str | None = None) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        if domain:
            terms = [dict(r) for r in conn.execute(
                "SELECT * FROM glossary_terms WHERE domain = ? ORDER BY term_en",
                (domain,),
            ).fetchall()]
        else:
            terms = [dict(r) for r in conn.execute(
                "SELECT * FROM glossary_terms ORDER BY term_en"
            ).fetchall()]
        domains = [r[0] for r in conn.execute(
            "SELECT DISTINCT domain FROM glossary_terms WHERE domain IS NOT NULL ORDER BY domain"
        ).fetchall()]
    return templates.TemplateResponse(
        "translate_assist/partials/glossary_panel.html",
        {"request": request, "terms": terms, "domains": domains},
    )


@router.get("/translation-memory/partial", response_class=HTMLResponse)
async def translation_memory_partial(request: Request, q: str = "") -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        if q:
            entries = [dict(r) for r in conn.execute(
                "SELECT * FROM translation_memory "
                "WHERE source_text LIKE ? OR translated_text LIKE ? "
                "ORDER BY quality_score DESC LIMIT 50",
                (f"%{q}%", f"%{q}%"),
            ).fetchall()]
        else:
            entries = [dict(r) for r in conn.execute(
                "SELECT * FROM translation_memory ORDER BY created_at DESC LIMIT 50"
            ).fetchall()]
    return templates.TemplateResponse(
        "translate_assist/partials/translation_memory.html",
        {"request": request, "entries": entries, "query": q},
    )
