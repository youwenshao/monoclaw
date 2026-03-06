"""DiscoveryAssistant FastAPI routes."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/discovery-assistant", tags=["DiscoveryAssistant"])
templates = Jinja2Templates(directory="legal/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "discovery-assistant", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["discovery_assistant"]


def _archives_dir(request: Request) -> Path:
    d: Path = request.app.state.workspace / "discovery" / "archives"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _index_dir(request: Request) -> Path:
    d: Path = request.app.state.workspace / "discovery" / "search_index"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Pydantic models ───────────────────────────────────────────────────────

class TagRequest(BaseModel):
    tag_name: str
    tagged_by: str = "user"


class BatchTagRequest(BaseModel):
    doc_ids: list[int]
    privilege_status: str | None = None
    tag_name: str | None = None
    tagged_by: str = "user"


# ── Main page ─────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def discovery_assistant_page(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        email_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type = 'email'"
        ).fetchone()[0]
        attachment_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type = 'attachment'"
        ).fetchone()[0]
        standalone_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE doc_type = 'standalone'"
        ).fetchone()[0]
        privileged_count = conn.execute(
            "SELECT COUNT(*) FROM classifications WHERE privilege_status = 'privileged'"
        ).fetchone()[0]
        needs_review_count = conn.execute(
            "SELECT COUNT(*) FROM classifications WHERE privilege_status = 'needs_review'"
        ).fetchone()[0]
        duplicate_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE is_duplicate = 1"
        ).fetchone()[0]
        classified_count = conn.execute(
            "SELECT COUNT(DISTINCT document_id) FROM classifications"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "discovery_assistant/index.html",
        _ctx(
            request,
            total_docs=total_docs,
            email_count=email_count,
            attachment_count=attachment_count,
            standalone_count=standalone_count,
            privileged_count=privileged_count,
            needs_review_count=needs_review_count,
            duplicate_count=duplicate_count,
            classified_count=classified_count,
        ),
    )


# ── Ingest ────────────────────────────────────────────────────────────────

@router.post("/ingest")
async def ingest_archive(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    from legal.discovery_assistant.email_parser import (
        extract_attachment_text,
        parse_eml,
        parse_mbox,
    )
    from legal.discovery_assistant.deduplicator import compute_hashes
    from legal.discovery_assistant.keyword_search import add_document_to_index

    db = _db(request)
    archives = _archives_dir(request)
    idx_dir = _index_dir(request)
    filename = file.filename or "unnamed"
    save_path = archives / filename

    content = await file.read()
    save_path.write_bytes(content)

    messages: list[dict[str, Any]] = []
    if filename.lower().endswith(".mbox"):
        messages = parse_mbox(save_path)
    elif filename.lower().endswith(".eml"):
        messages = [parse_eml(save_path)]
    else:
        body_text = content.decode("utf-8", errors="replace")
        md5, sha256 = compute_hashes(body_text)
        with get_db(db) as conn:
            cursor = conn.execute(
                """INSERT INTO documents
                   (source_file, doc_type, date_created, author, recipients, subject,
                    body_text, hash_md5, hash_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (filename, "standalone", datetime.now().isoformat(), None, None,
                 filename, body_text, md5, sha256),
            )
            doc_id = cursor.lastrowid

        add_document_to_index(idx_dir, {
            "id": doc_id, "source_file": filename, "author": "",
            "subject": filename, "body_text": body_text, "date_created": datetime.now().isoformat(),
        })

        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="discovery-assistant",
            summary=f"Ingested standalone document: {filename}",
        )
        return {"ingested": 1, "documents": [doc_id]}

    ingested_ids: list[int] = []
    for msg in messages:
        body = msg.get("body", "")
        md5, sha256 = compute_hashes(body)

        with get_db(db) as conn:
            cursor = conn.execute(
                """INSERT INTO documents
                   (source_file, doc_type, date_created, author, recipients, subject,
                    body_text, hash_md5, hash_sha256)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    msg.get("source_file", filename),
                    "email",
                    msg.get("date", ""),
                    msg.get("from", ""),
                    msg.get("to", ""),
                    msg.get("subject", ""),
                    body,
                    md5,
                    sha256,
                ),
            )
            email_doc_id = cursor.lastrowid
            ingested_ids.append(email_doc_id)

        add_document_to_index(idx_dir, {
            "id": email_doc_id, "source_file": msg.get("source_file", filename),
            "author": msg.get("from", ""), "subject": msg.get("subject", ""),
            "body_text": body, "date_created": msg.get("date", ""),
        })

        for att in msg.get("attachment_data", []):
            att_bytes = att.get("data")
            if not att_bytes:
                continue
            att_text = extract_attachment_text(att_bytes, att.get("content_type", ""))
            if not att_text:
                att_text = f"[Binary attachment: {att['filename']}]"

            att_md5, att_sha256 = compute_hashes(att_text)
            with get_db(db) as conn:
                cursor = conn.execute(
                    """INSERT INTO documents
                       (source_file, doc_type, date_created, author, recipients, subject,
                        body_text, hash_md5, hash_sha256)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        att["filename"],
                        "attachment",
                        msg.get("date", ""),
                        msg.get("from", ""),
                        msg.get("to", ""),
                        f"Attachment: {att['filename']}",
                        att_text,
                        att_md5,
                        att_sha256,
                    ),
                )
                att_doc_id = cursor.lastrowid
                ingested_ids.append(att_doc_id)

            add_document_to_index(idx_dir, {
                "id": att_doc_id, "source_file": att["filename"],
                "author": msg.get("from", ""), "subject": f"Attachment: {att['filename']}",
                "body_text": att_text, "date_created": msg.get("date", ""),
            })

    from legal.discovery_assistant.deduplicator import mark_duplicates
    dup_count = mark_duplicates(db)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="discovery-assistant",
        summary=f"Ingested {len(ingested_ids)} documents from {filename} ({dup_count} duplicates found)",
    )

    return {"ingested": len(ingested_ids), "duplicates_found": dup_count, "documents": ingested_ids}


# ── Document list ─────────────────────────────────────────────────────────

@router.get("/documents")
async def list_documents(
    request: Request,
    page: int = 1,
    per_page: int = 20,
    doc_type: str | None = None,
    privilege_status: str | None = None,
) -> dict[str, Any]:
    db = _db(request)
    offset = (page - 1) * per_page

    where_clauses: list[str] = []
    params: list[Any] = []

    if doc_type:
        where_clauses.append("d.doc_type = ?")
        params.append(doc_type)
    if privilege_status:
        where_clauses.append("c.privilege_status = ?")
        params.append(privilege_status)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    join_sql = "LEFT JOIN classifications c ON c.document_id = d.id"
    if privilege_status:
        join_sql = "JOIN classifications c ON c.document_id = d.id"

    with get_db(db) as conn:
        count_row = conn.execute(
            f"SELECT COUNT(DISTINCT d.id) FROM documents d {join_sql} {where_sql}",
            params,
        ).fetchone()
        total = count_row[0]

        rows = conn.execute(
            f"""SELECT DISTINCT d.*, c.relevance_tier, c.privilege_status, c.privilege_type,
                       c.confidence_score
                FROM documents d {join_sql} {where_sql}
                ORDER BY d.ingested_at DESC
                LIMIT ? OFFSET ?""",
            [*params, per_page, offset],
        ).fetchall()

    documents = [dict(r) for r in rows]

    with get_db(db) as conn:
        for doc in documents:
            tag_rows = conn.execute(
                "SELECT tag_name, tagged_by, tag_date FROM tags WHERE document_id = ?",
                (doc["id"],),
            ).fetchall()
            doc["tags"] = [dict(t) for t in tag_rows]

    return {
        "documents": documents,
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }


# ── Classify ──────────────────────────────────────────────────────────────

@router.post("/classify/{doc_id}")
async def classify_document(request: Request, doc_id: int) -> dict[str, Any]:
    from legal.discovery_assistant.privilege_detector import detect_privilege
    from legal.discovery_assistant.relevance_scorer import score_relevance

    db = _db(request)
    llm = request.app.state.llm

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)

    privilege_result = await detect_privilege(doc, llm=llm)

    config = request.app.state.config
    case_keywords = config.extra.get("case_keywords", [])
    if isinstance(case_keywords, str):
        case_keywords = [kw.strip() for kw in case_keywords.split(",") if kw.strip()]
    relevance_result = await score_relevance(doc, case_keywords, llm=llm)

    with get_db(db) as conn:
        existing = conn.execute(
            "SELECT id FROM classifications WHERE document_id = ?", (doc_id,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE classifications SET
                      relevance_tier = ?, privilege_status = ?, privilege_type = ?,
                      confidence_score = ?, review_date = CURRENT_TIMESTAMP
                   WHERE document_id = ?""",
                (
                    relevance_result["relevance_tier"],
                    privilege_result["privilege_status"],
                    privilege_result.get("privilege_type"),
                    privilege_result["confidence_score"],
                    doc_id,
                ),
            )
        else:
            conn.execute(
                """INSERT INTO classifications
                   (document_id, relevance_tier, privilege_status, privilege_type,
                    confidence_score, review_date)
                   VALUES (?,?,?,?,?,CURRENT_TIMESTAMP)""",
                (
                    doc_id,
                    relevance_result["relevance_tier"],
                    privilege_result["privilege_status"],
                    privilege_result.get("privilege_type"),
                    privilege_result["confidence_score"],
                ),
            )

        if privilege_result["privilege_status"] in ("privileged", "partial"):
            existing_log = conn.execute(
                "SELECT id FROM privilege_log WHERE document_id = ?", (doc_id,)
            ).fetchone()
            if not existing_log:
                conn.execute(
                    """INSERT INTO privilege_log
                       (document_id, log_date, description, privilege_basis, status)
                       VALUES (?, date('now'), ?, ?, 'draft')""",
                    (doc_id, doc.get("subject", ""), privilege_result.get("privilege_type", "")),
                )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="discovery-assistant",
        summary=(
            f"Classified doc #{doc_id}: "
            f"{relevance_result['relevance_tier']}, "
            f"{privilege_result['privilege_status']}"
        ),
        requires_human_action=privilege_result["privilege_status"] == "needs_review",
    )

    return {
        "document_id": doc_id,
        "privilege": privilege_result,
        "relevance": relevance_result,
    }


# ── Tagging ───────────────────────────────────────────────────────────────

@router.post("/tag/{doc_id}")
async def tag_document(request: Request, doc_id: int, body: TagRequest) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    with get_db(db) as conn:
        conn.execute(
            "INSERT INTO tags (document_id, tag_name, tagged_by) VALUES (?,?,?)",
            (doc_id, body.tag_name, body.tagged_by),
        )

    return {"document_id": doc_id, "tag_name": body.tag_name, "tagged_by": body.tagged_by}


@router.post("/batch-tag")
async def batch_tag(request: Request, body: BatchTagRequest) -> dict[str, Any]:
    db = _db(request)
    updated = 0

    with get_db(db) as conn:
        for doc_id in body.doc_ids:
            row = conn.execute("SELECT id FROM documents WHERE id = ?", (doc_id,)).fetchone()
            if not row:
                continue

            if body.tag_name:
                conn.execute(
                    "INSERT INTO tags (document_id, tag_name, tagged_by) VALUES (?,?,?)",
                    (doc_id, body.tag_name, body.tagged_by),
                )
                updated += 1

            if body.privilege_status:
                existing = conn.execute(
                    "SELECT id FROM classifications WHERE document_id = ?", (doc_id,)
                ).fetchone()
                if existing:
                    conn.execute(
                        """UPDATE classifications SET privilege_status = ?,
                              reviewer_override = ?, reviewed_by = ?,
                              review_date = CURRENT_TIMESTAMP
                           WHERE document_id = ?""",
                        (body.privilege_status, body.privilege_status, body.tagged_by, doc_id),
                    )
                else:
                    conn.execute(
                        """INSERT INTO classifications
                           (document_id, privilege_status, reviewer_override, reviewed_by,
                            review_date)
                           VALUES (?,?,?,?,CURRENT_TIMESTAMP)""",
                        (doc_id, body.privilege_status, body.privilege_status, body.tagged_by),
                    )
                updated += 1

    return {"updated": updated, "doc_ids": body.doc_ids}


# ── Search ────────────────────────────────────────────────────────────────

@router.get("/search")
async def search(request: Request, q: str = "", page: int = 1, per_page: int = 20) -> dict[str, Any]:
    from legal.discovery_assistant.keyword_search import search_documents

    if not q.strip():
        return {"results": [], "total": 0, "page": page, "per_page": per_page, "query": ""}

    idx_dir = _index_dir(request)
    return search_documents(idx_dir, q, page=page, per_page=per_page)


# ── Timeline ──────────────────────────────────────────────────────────────

@router.get("/timeline", response_class=HTMLResponse)
async def timeline_view(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT d.*, c.relevance_tier, c.privilege_status, c.privilege_type
               FROM documents d
               LEFT JOIN classifications c ON c.document_id = d.id
               WHERE d.date_created IS NOT NULL AND d.date_created != ''
               ORDER BY d.date_created ASC"""
        ).fetchall()

    documents = [dict(r) for r in rows]

    return templates.TemplateResponse(
        "discovery_assistant/partials/timeline.html",
        {"request": request, "documents": documents},
    )


# ── Privilege log export ──────────────────────────────────────────────────

@router.get("/privilege-log/export")
async def export_privilege_log(request: Request) -> FileResponse:
    from legal.discovery_assistant.privilege_log import generate_privilege_log

    db = _db(request)
    tmp_dir = Path(tempfile.mkdtemp())
    output_path = tmp_dir / f"privilege_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    generate_privilege_log(db, output_path)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="discovery-assistant",
        summary="Privilege log exported as Excel",
    )

    return FileResponse(
        path=str(output_path),
        filename=output_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/document-preview/partial", response_class=HTMLResponse)
async def document_preview_partial(request: Request, doc_id: int) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)

    with get_db(db) as conn:
        classification = conn.execute(
            "SELECT * FROM classifications WHERE document_id = ?", (doc_id,)
        ).fetchone()
        tags = conn.execute(
            "SELECT * FROM tags WHERE document_id = ?", (doc_id,)
        ).fetchall()

    doc["classification"] = dict(classification) if classification else None
    doc["tags"] = [dict(t) for t in tags]

    return templates.TemplateResponse(
        "discovery_assistant/partials/document_preview.html",
        {"request": request, "document": doc},
    )


@router.get("/privilege-tagger/partial", response_class=HTMLResponse)
async def privilege_tagger_partial(request: Request, doc_id: int) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)

    with get_db(db) as conn:
        classification = conn.execute(
            "SELECT * FROM classifications WHERE document_id = ?", (doc_id,)
        ).fetchone()

    doc["classification"] = dict(classification) if classification else None

    return templates.TemplateResponse(
        "discovery_assistant/partials/privilege_tagger.html",
        {"request": request, "document": doc},
    )


@router.get("/search-results/partial", response_class=HTMLResponse)
async def search_results_partial(
    request: Request, q: str = "", page: int = 1, per_page: int = 20,
) -> HTMLResponse:
    from legal.discovery_assistant.keyword_search import search_documents

    results: dict[str, Any] = {"results": [], "total": 0, "page": page, "per_page": per_page, "query": q}
    if q.strip():
        idx_dir = _index_dir(request)
        results = search_documents(idx_dir, q, page=page, per_page=per_page)

    return templates.TemplateResponse(
        "discovery_assistant/partials/search_results.html",
        {"request": request, **results},
    )
