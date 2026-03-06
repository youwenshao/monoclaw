"""InvoiceOCR Pro FastAPI routes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/invoice-ocr", tags=["InvoiceOCR"])

templates = Jinja2Templates(directory="accounting/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "invoice-ocr", **extra}


def _uploads_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "incoming"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def invoice_ocr_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'pending_review'"
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'approved'"
        ).fetchone()[0]
        pushed = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'pushed'"
        ).fetchone()[0]
        today_count = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE DATE(created_at) = DATE('now')"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "invoice_ocr/index.html",
        _ctx(
            request,
            total=total,
            pending=pending,
            approved=approved,
            pushed=pushed,
            today_count=today_count,
        ),
    )


# ── Upload ─────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_invoice(
    request: Request,
    file: UploadFile = File(...),
    source: str = "manual_upload",
) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]
    uploads = _uploads_dir(request)

    file_path = uploads / (file.filename or "unnamed")
    content = await file.read()
    file_path.write_bytes(content)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO invoices (source, source_file, total_amount, status)
               VALUES (?, ?, 0, 'pending_review')""",
            (source, str(file_path)),
        )
        invoice_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="invoice-ocr",
        summary=f"Invoice uploaded: {file.filename} (source: {source})",
    )

    return {"invoice_id": invoice_id, "file_path": str(file_path), "status": "pending_review"}


# ── Process via OCR ────────────────────────────────────────────────────────

@router.post("/process/{invoice_id}")
async def process_invoice(request: Request, invoice_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")

    doc = dict(row)
    file_path = doc.get("source_file")
    if not file_path or not Path(file_path).exists():
        raise HTTPException(status_code=400, detail="Source file missing")

    from accounting.invoice_ocr.ocr.vision_engine import process_image
    from accounting.invoice_ocr.extraction.invoice_parser import parse_invoice

    ocr_result = process_image(file_path)
    parsed = parse_invoice(ocr_result)

    with get_db(db) as conn:
        conn.execute(
            """UPDATE invoices SET
                supplier_name = ?, invoice_number = ?, invoice_date = ?,
                currency = ?, subtotal = ?, tax_amount = ?, total_amount = ?,
                ocr_confidence = ?, status = 'pending_review'
               WHERE id = ?""",
            (
                parsed.get("supplier_name"),
                parsed.get("invoice_number"),
                parsed.get("invoice_date"),
                parsed.get("currency", "HKD"),
                parsed.get("subtotal"),
                parsed.get("tax_amount"),
                parsed.get("total_amount", 0),
                ocr_result.get("confidence", 0),
                invoice_id,
            ),
        )

        for item in parsed.get("line_items", []):
            conn.execute(
                """INSERT INTO line_items (invoice_id, description, quantity, unit_price, amount)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    invoice_id,
                    item.get("description"),
                    item.get("quantity"),
                    item.get("unit_price"),
                    item.get("amount", 0),
                ),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="invoice-ocr",
        summary=f"OCR complete for invoice #{invoice_id}: {parsed.get('supplier_name', 'unknown')}",
    )

    return {
        "invoice_id": invoice_id,
        "status": "pending_review",
        "confidence": ocr_result.get("confidence", 0),
        "parsed": parsed,
    }


# ── List invoices ──────────────────────────────────────────────────────────

@router.get("/invoices")
async def list_invoices(
    request: Request,
    status: str | None = None,
) -> list[dict[str, Any]]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM invoices WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM invoices ORDER BY created_at DESC"
            ).fetchall()

    return [dict(r) for r in rows]


# ── Single invoice with line items ─────────────────────────────────────────

@router.get("/invoices/{invoice_id}")
async def get_invoice(request: Request, invoice_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice = dict(row)
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM line_items WHERE invoice_id = ? ORDER BY id",
            (invoice_id,),
        ).fetchall()]

    invoice["line_items"] = items
    return invoice


# ── Approve ────────────────────────────────────────────────────────────────

@router.post("/invoices/{invoice_id}/approve")
async def approve_invoice(request: Request, invoice_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")
        conn.execute("UPDATE invoices SET status = 'approved' WHERE id = ?", (invoice_id,))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="invoice-ocr",
        summary=f"Invoice #{invoice_id} approved",
    )

    return {"invoice_id": invoice_id, "status": "approved"}


# ── Batch approve ──────────────────────────────────────────────────────────

@router.post("/invoices/batch-approve")
async def batch_approve(request: Request) -> dict[str, Any]:
    body = await request.json()
    invoice_ids: list[int] = body.get("invoice_ids", [])
    if not invoice_ids:
        raise HTTPException(status_code=400, detail="No invoice IDs provided")

    db = request.app.state.db_paths["invoice_ocr"]
    approved: list[int] = []

    with get_db(db) as conn:
        for iid in invoice_ids:
            row = conn.execute("SELECT id FROM invoices WHERE id = ?", (iid,)).fetchone()
            if row:
                conn.execute("UPDATE invoices SET status = 'approved' WHERE id = ?", (iid,))
                approved.append(iid)

    if approved:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="invoice-ocr",
            summary=f"Batch approved {len(approved)} invoices: {approved}",
        )

    return {"approved": approved, "count": len(approved)}


# ── Duplicate check ────────────────────────────────────────────────────────

@router.get("/duplicates/{invoice_id}")
async def check_duplicates(request: Request, invoice_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Invoice not found")

    invoice = dict(row)

    from accounting.invoice_ocr.accounting_push.duplicate import check_duplicate

    result = check_duplicate(
        invoice_number=invoice.get("invoice_number"),
        supplier_name=invoice.get("supplier_name"),
        total_amount=invoice.get("total_amount"),
        db_path=db,
        exclude_id=invoice_id,
    )

    if result["is_duplicate"]:
        with get_db(db) as conn:
            conn.execute("UPDATE invoices SET duplicate_flag = 1 WHERE id = ?", (invoice_id,))

    return {"invoice_id": invoice_id, **result}


# ── Stats ──────────────────────────────────────────────────────────────────

@router.get("/stats")
async def processing_stats(request: Request) -> dict[str, Any]:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        total = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        by_status = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT status, COUNT(*) FROM invoices GROUP BY status"
            ).fetchall()
        }
        avg_confidence = conn.execute(
            "SELECT AVG(ocr_confidence) FROM invoices WHERE ocr_confidence IS NOT NULL"
        ).fetchone()[0] or 0.0
        total_amount = conn.execute(
            "SELECT SUM(total_amount) FROM invoices WHERE status IN ('approved', 'pushed')"
        ).fetchone()[0] or 0.0
        top_suppliers = [dict(r) for r in conn.execute(
            """SELECT supplier_name, COUNT(*) as count, SUM(total_amount) as total
               FROM invoices WHERE supplier_name IS NOT NULL
               GROUP BY supplier_name ORDER BY count DESC LIMIT 10"""
        ).fetchall()]

    return {
        "total_invoices": total,
        "by_status": by_status,
        "avg_confidence": round(avg_confidence, 4),
        "total_approved_amount": round(total_amount, 2),
        "top_suppliers": top_suppliers,
    }


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/queue/partial", response_class=HTMLResponse)
async def queue_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["invoice_ocr"]

    with get_db(db) as conn:
        invoices = [dict(r) for r in conn.execute(
            "SELECT * FROM invoices ORDER BY created_at DESC LIMIT 30"
        ).fetchall()]

    return templates.TemplateResponse(
        "invoice_ocr/partials/queue_list.html",
        {"request": request, "invoices": invoices},
    )


@router.get("/editor/partial", response_class=HTMLResponse)
async def editor_partial(request: Request, invoice_id: int | None = None) -> HTMLResponse:
    db = request.app.state.db_paths["invoice_ocr"]
    invoice: dict[str, Any] | None = None
    line_items: list[dict[str, Any]] = []

    if invoice_id:
        with get_db(db) as conn:
            row = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
            if row:
                invoice = dict(row)
                line_items = [dict(r) for r in conn.execute(
                    "SELECT * FROM line_items WHERE invoice_id = ? ORDER BY id",
                    (invoice_id,),
                ).fetchall()]

    return templates.TemplateResponse(
        "invoice_ocr/partials/invoice_editor.html",
        {"request": request, "invoice": invoice, "line_items": line_items},
    )
