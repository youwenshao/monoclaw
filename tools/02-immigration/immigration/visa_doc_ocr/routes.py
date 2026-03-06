"""VisaDoc OCR FastAPI routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/visa-doc-ocr", tags=["VisaDocOCR"])

templates = Jinja2Templates(directory="immigration/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "visa-doc-ocr", **extra}


def _uploads_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "documents" / "incoming"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def visa_doc_ocr_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["visa_doc_ocr"]

    with get_db(db) as conn:
        clients = [dict(r) for r in conn.execute(
            "SELECT * FROM clients ORDER BY created_at DESC"
        ).fetchall()]
        total_docs = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        pending_docs = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status = 'pending'"
        ).fetchone()[0]
        review_docs = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status = 'review'"
        ).fetchone()[0]
        processed_docs = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE status = 'processed'"
        ).fetchone()[0]
        avg_confidence = conn.execute(
            "SELECT AVG(confidence_score) FROM documents WHERE confidence_score IS NOT NULL"
        ).fetchone()[0] or 0.0

    return templates.TemplateResponse(
        "visa_doc_ocr/index.html",
        _ctx(
            request,
            clients=clients,
            total_docs=total_docs,
            pending_docs=pending_docs,
            review_docs=review_docs,
            processed_docs=processed_docs,
            avg_confidence=round(avg_confidence, 2),
        ),
    )


# ── Upload ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    client_id: int | None = None,
    doc_type: str = "unknown",
) -> dict[str, Any]:
    db = request.app.state.db_paths["visa_doc_ocr"]
    uploads = _uploads_dir(request)

    file_path = uploads / (file.filename or "unnamed")
    content = await file.read()
    file_path.write_bytes(content)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO documents (client_id, doc_type, file_path, status)
               VALUES (?,?,?,?)""",
            (client_id, doc_type, str(file_path), "pending"),
        )
        doc_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="visa-doc-ocr",
        summary=f"Document uploaded: {file.filename} (type: {doc_type})",
    )

    return {"document_id": doc_id, "file_path": str(file_path), "status": "pending"}


# ── Process document via OCR ───────────────────────────────────────────────

@router.post("/process/{doc_id}")
async def process_document(request: Request, doc_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["visa_doc_ocr"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)
    file_path = Path(doc["file_path"])

    from immigration.visa_doc_ocr.ocr.vision_engine import process_image
    from immigration.visa_doc_ocr.ocr.confidence import score_fields

    ocr_result = process_image(str(file_path), doc["doc_type"])
    confidence = score_fields(ocr_result)

    config = request.app.state.config
    auto_threshold = config.extra.get("confidence_threshold_auto", 0.85)
    review_threshold = config.extra.get("confidence_threshold_review", 0.70)

    if confidence >= auto_threshold:
        status = "processed"
    elif confidence >= review_threshold:
        status = "review"
    else:
        status = "rejected"

    with get_db(db) as conn:
        conn.execute(
            """UPDATE documents SET ocr_result = ?, confidence_score = ?, status = ?,
               processed_at = CURRENT_TIMESTAMP WHERE id = ?""",
            (json.dumps(ocr_result), confidence, status, doc_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="visa-doc-ocr",
        summary=f"OCR complete for doc #{doc_id}: {status} (confidence: {confidence:.0%})",
        requires_human_action=status == "review",
    )

    return {"document_id": doc_id, "status": status, "confidence": confidence, "result": ocr_result}


# ── Get document details ──────────────────────────────────────────────────

@router.get("/documents/{doc_id}")
async def get_document(request: Request, doc_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["visa_doc_ocr"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = dict(row)
    if doc.get("ocr_result"):
        doc["ocr_result"] = json.loads(doc["ocr_result"])
    return doc


# ── Completeness check ────────────────────────────────────────────────────

@router.get("/completeness/{client_id}")
async def check_completeness(request: Request, client_id: int, scheme: str = "GEP") -> dict[str, Any]:
    db = request.app.state.db_paths["visa_doc_ocr"]

    from immigration.visa_doc_ocr.validators.completeness import check_document_completeness
    from immigration.visa_doc_ocr.validators.expiry import check_document_expiry

    with get_db(db) as conn:
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM documents WHERE client_id = ? AND status IN ('processed', 'review')",
            (client_id,),
        ).fetchall()]

    result = check_document_completeness(scheme, docs)
    expiry_flags = check_document_expiry(docs)

    return {
        "client_id": client_id,
        "scheme": scheme,
        "completeness": result,
        "expiry_flags": expiry_flags,
    }


# ── Approve and send to FormAutoFill ──────────────────────────────────────

@router.post("/approve/{doc_id}")
async def approve_document(request: Request, doc_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["visa_doc_ocr"]
    shared_db = request.app.state.db_paths["shared"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)
    with get_db(db) as conn:
        conn.execute("UPDATE documents SET status = 'approved' WHERE id = ?", (doc_id,))

    if doc.get("client_id") and doc.get("ocr_result"):
        ocr_data = json.loads(doc["ocr_result"])
        client_row = None
        with get_db(db) as conn:
            client_row = conn.execute(
                "SELECT * FROM clients WHERE id = ?", (doc["client_id"],)
            ).fetchone()

        if client_row:
            client = dict(client_row)
            with get_db(shared_db) as conn:
                existing = conn.execute(
                    "SELECT id FROM shared_clients WHERE ocr_client_id = ?",
                    (client["id"],),
                ).fetchone()
                if not existing:
                    conn.execute(
                        """INSERT INTO shared_clients
                           (name_en, name_zh, hkid, passport_number, nationality, phone, email, ocr_client_id)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (client["name_en"], client.get("name_zh"), client.get("hkid"),
                         client.get("passport_number"), client.get("nationality"),
                         client.get("phone"), client.get("email"), client["id"]),
                    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="visa-doc-ocr",
        summary=f"Document #{doc_id} approved and synced to shared client DB",
    )

    return {"document_id": doc_id, "status": "approved"}


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/batch-queue/partial", response_class=HTMLResponse)
async def batch_queue_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["visa_doc_ocr"]
    with get_db(db) as conn:
        docs = [dict(r) for r in conn.execute(
            "SELECT * FROM documents ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
    return templates.TemplateResponse(
        "visa_doc_ocr/partials/batch_queue.html",
        {"request": request, "documents": docs},
    )


@router.get("/document-viewer/partial", response_class=HTMLResponse)
async def document_viewer_partial(request: Request, doc_id: int) -> HTMLResponse:
    db = request.app.state.db_paths["visa_doc_ocr"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = dict(row)
    if doc.get("ocr_result"):
        doc["ocr_result"] = json.loads(doc["ocr_result"])
    return templates.TemplateResponse(
        "visa_doc_ocr/partials/document_viewer.html",
        {"request": request, "document": doc},
    )
