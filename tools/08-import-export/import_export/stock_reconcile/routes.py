"""StockReconcile FastAPI routes — manifest upload, reconciliation, discrepancy tracking."""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/stock-reconcile", tags=["StockReconcile"])

templates = Jinja2Templates(directory="import_export/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "stock-reconcile", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def stock_reconcile_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["stock_reconcile"]

    with get_db(db) as conn:
        shipments_count = conn.execute("SELECT COUNT(*) FROM shipments").fetchone()[0]
        reconciled_count = conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status IN ('reconciled', 'closed')"
        ).fetchone()[0]
        active_discrepancies = conn.execute(
            "SELECT COUNT(*) FROM reconciliation_results WHERE status != 'matched'"
        ).fetchone()[0]
        pending_receipts = conn.execute(
            """SELECT COUNT(*) FROM shipments s
               WHERE s.status NOT IN ('reconciled', 'closed')
               AND NOT EXISTS (
                   SELECT 1 FROM warehouse_receipts wr WHERE wr.shipment_id = s.id
               )"""
        ).fetchone()[0]

    return templates.TemplateResponse(
        "stock_reconcile/index.html",
        _ctx(
            request,
            shipments_count=shipments_count,
            reconciled_count=reconciled_count,
            active_discrepancies=active_discrepancies,
            pending_receipts=pending_receipts,
        ),
    )


# ── Manifest upload ───────────────────────────────────────────────────────

@router.post("/api/upload-manifest")
async def upload_manifest(request: Request, file: UploadFile) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    suffix = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "pdf"
    with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    from import_export.stock_reconcile.ingestion.manifest_parser import ManifestParser
    parser = ManifestParser()
    try:
        parsed = parser.parse(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse manifest: {e}")

    bl_number = parsed.get("bl_number")
    vessel = parsed.get("vessel")
    voyage = parsed.get("voyage")
    items = parsed.get("items", [])

    with get_db(db) as conn:
        existing = None
        if bl_number:
            existing = conn.execute(
                "SELECT id FROM shipments WHERE bl_number = ?", (bl_number,)
            ).fetchone()

        if existing:
            shipment_id = existing["id"]
        else:
            ref = f"SHP-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            cursor = conn.execute(
                """INSERT INTO shipments (shipment_reference, bl_number, vessel_name, voyage, status)
                   VALUES (?,?,?,?,?)""",
                (ref, bl_number, vessel, voyage, "arrived"),
            )
            shipment_id = cursor.lastrowid

        for item in items:
            conn.execute(
                """INSERT INTO manifest_items
                   (shipment_id, item_description, sku, quantity, unit, weight_kg,
                    carton_count, source_document)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    shipment_id,
                    item.get("description"),
                    item.get("sku"),
                    item.get("quantity"),
                    item.get("unit"),
                    item.get("weight_kg"),
                    item.get("carton_count"),
                    file.filename,
                ),
            )

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    ShipmentTimeline.add_event(db, shipment_id, "manifest_uploaded", f"Manifest uploaded: {file.filename}")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="stock-reconcile",
        summary=f"Manifest uploaded for B/L {bl_number or 'N/A'} — {len(items)} items parsed",
    )

    return {
        "shipment_id": shipment_id,
        "bl_number": bl_number,
        "vessel": vessel,
        "items_parsed": len(items),
        "parsed_data": parsed,
    }


# ── Receipt upload ────────────────────────────────────────────────────────

@router.post("/api/upload-receipt")
async def upload_receipt(request: Request, file: UploadFile, shipment_id: int | None = None) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    suffix = file.filename.rsplit(".", 1)[-1].lower() if file.filename else "pdf"
    with tempfile.NamedTemporaryFile(suffix=f".{suffix}", delete=False) as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    from import_export.stock_reconcile.ingestion.warehouse_receipt_parser import WarehouseReceiptParser
    parser = WarehouseReceiptParser()
    try:
        parsed = parser.parse(tmp_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse receipt: {e}")

    receipt_number = parsed.get("receipt_number")
    items = parsed.get("items", [])

    if not shipment_id:
        with get_db(db) as conn:
            latest = conn.execute(
                """SELECT id FROM shipments
                   WHERE status NOT IN ('reconciled', 'closed')
                   ORDER BY created_at DESC LIMIT 1"""
            ).fetchone()
        if latest:
            shipment_id = latest["id"]
        else:
            raise HTTPException(status_code=400, detail="No shipment_id provided and no active shipment found")

    with get_db(db) as conn:
        shipment = conn.execute("SELECT id FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail=f"Shipment {shipment_id} not found")

        cursor = conn.execute(
            """INSERT INTO warehouse_receipts
               (shipment_id, receipt_number, received_date, warehouse, received_by)
               VALUES (?,?,?,?,?)""",
            (
                shipment_id,
                receipt_number,
                parsed.get("received_date") or datetime.now().strftime("%Y-%m-%d"),
                parsed.get("warehouse"),
                parsed.get("received_by"),
            ),
        )
        receipt_id = cursor.lastrowid

        for item in items:
            conn.execute(
                """INSERT INTO receipt_items
                   (receipt_id, item_description, sku, quantity_received, unit, condition)
                   VALUES (?,?,?,?,?,?)""",
                (
                    receipt_id,
                    item.get("description"),
                    item.get("sku"),
                    item.get("quantity_received"),
                    item.get("unit"),
                    item.get("condition", "good"),
                ),
            )

        conn.execute(
            "UPDATE shipments SET status = 'at_warehouse' WHERE id = ? AND status IN ('in_transit', 'arrived', 'gate_out')",
            (shipment_id,),
        )

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    ShipmentTimeline.add_event(db, shipment_id, "receipt_uploaded", f"Warehouse receipt {receipt_number or 'N/A'} uploaded — {len(items)} items")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="stock-reconcile",
        summary=f"Receipt uploaded for shipment #{shipment_id} — {len(items)} items",
    )

    return {
        "shipment_id": shipment_id,
        "receipt_id": receipt_id,
        "receipt_number": receipt_number,
        "items_parsed": len(items),
    }


# ── Shipments ─────────────────────────────────────────────────────────────

@router.get("/api/shipments")
async def list_shipments(request: Request) -> list[dict]:
    db = request.app.state.db_paths["stock_reconcile"]
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT s.*,
                      COUNT(DISTINCT mi.id) AS manifest_items,
                      COUNT(DISTINCT wr.id) AS receipt_count,
                      (SELECT COUNT(*) FROM reconciliation_results rr
                       WHERE rr.shipment_id = s.id AND rr.status != 'matched') AS discrepancy_count
               FROM shipments s
               LEFT JOIN manifest_items mi ON mi.shipment_id = s.id
               LEFT JOIN warehouse_receipts wr ON wr.shipment_id = s.id
               GROUP BY s.id
               ORDER BY s.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


class CreateShipmentRequest(BaseModel):
    shipment_reference: str | None = None
    bl_number: str | None = None
    bl_type: str = "master"
    master_bl: str | None = None
    vessel_name: str | None = None
    voyage: str | None = None
    origin_port: str | None = None
    arrival_date: str | None = None
    container_numbers: str | None = None
    load_type: str = "FCL"
    consignee: str | None = None


@router.post("/api/shipments")
async def create_shipment(request: Request, body: CreateShipmentRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    ref = body.shipment_reference or f"SHP-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO shipments
               (shipment_reference, bl_number, bl_type, master_bl, vessel_name,
                voyage, origin_port, arrival_date, container_numbers, load_type,
                consignee, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                ref, body.bl_number, body.bl_type, body.master_bl,
                body.vessel_name, body.voyage, body.origin_port,
                body.arrival_date, body.container_numbers, body.load_type,
                body.consignee, "in_transit",
            ),
        )
        shipment_id = cursor.lastrowid

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    ShipmentTimeline.add_event(db, shipment_id, "created", f"Shipment {ref} created")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="stock-reconcile",
        summary=f"Shipment created: {ref} (B/L: {body.bl_number or 'N/A'})",
    )

    return {"shipment_id": shipment_id, "shipment_reference": ref}


@router.get("/api/shipments/{shipment_id}")
async def get_shipment(request: Request, shipment_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    with get_db(db) as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

        manifest_items = conn.execute(
            "SELECT * FROM manifest_items WHERE shipment_id = ?", (shipment_id,)
        ).fetchall()

        receipts = conn.execute(
            "SELECT * FROM warehouse_receipts WHERE shipment_id = ?", (shipment_id,)
        ).fetchall()

        receipt_items: list[dict] = []
        for wr in receipts:
            items = conn.execute(
                "SELECT * FROM receipt_items WHERE receipt_id = ?", (wr["id"],)
            ).fetchall()
            receipt_items.extend([dict(i) for i in items])

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    timeline = ShipmentTimeline.get_timeline(db, shipment_id)

    return {
        "shipment": dict(shipment),
        "manifest_items": [dict(m) for m in manifest_items],
        "receipts": [dict(r) for r in receipts],
        "receipt_items": receipt_items,
        "timeline": timeline,
    }


# ── Reconciliation ────────────────────────────────────────────────────────

@router.post("/api/reconcile/{shipment_id}")
async def reconcile_shipment(request: Request, shipment_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    with get_db(db) as conn:
        shipment = conn.execute("SELECT * FROM shipments WHERE id = ?", (shipment_id,)).fetchone()
        if not shipment:
            raise HTTPException(status_code=404, detail="Shipment not found")

    from import_export.stock_reconcile.reconciliation.matching_engine import MatchingEngine
    llm = getattr(request.app.state, "llm", None)
    engine = MatchingEngine(fuzzy_threshold=80, llm=llm)

    load_type = shipment["load_type"]
    if load_type == "LCL":
        from import_export.stock_reconcile.reconciliation.lcl_reconciler import LCLReconciler
        result = LCLReconciler().reconcile(str(db), shipment_id, engine)
    else:
        from import_export.stock_reconcile.reconciliation.fcl_reconciler import FCLReconciler
        result = FCLReconciler().reconcile(str(db), shipment_id, engine)

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    ShipmentTimeline.add_event(db, shipment_id, "reconciliation_completed",
        f"Reconciliation complete — {result.get('total_items', 0)} items processed")

    disc_count = sum(1 for r in result.get("results", []) if r.get("status") != "matched")
    if disc_count > 0:
        ShipmentTimeline.add_event(db, shipment_id, "discrepancy_found",
            f"{disc_count} discrepancies found")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="stock-reconcile",
        summary=f"Shipment #{shipment_id} reconciled — {disc_count} discrepancies",
        requires_human_action=disc_count > 0,
    )

    return result


@router.get("/api/reconciliation-results/{shipment_id}")
async def get_reconciliation_results(request: Request, shipment_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    from import_export.stock_reconcile.reports.reconciliation_report import ReconciliationReport
    try:
        report = ReconciliationReport.generate(str(db), shipment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    return report


# ── Discrepancies ─────────────────────────────────────────────────────────

@router.get("/api/discrepancies")
async def list_discrepancies(request: Request, shipment_id: int | None = None) -> list[dict]:
    db = request.app.state.db_paths["stock_reconcile"]

    from import_export.stock_reconcile.reconciliation.discrepancy_handler import DiscrepancyHandler
    return DiscrepancyHandler.get_discrepancies(str(db), shipment_id)


# ── Claims ────────────────────────────────────────────────────────────────

class GenerateClaimRequest(BaseModel):
    shipment_id: int


@router.post("/api/generate-claim")
async def generate_claim(request: Request, body: GenerateClaimRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["stock_reconcile"]

    from import_export.stock_reconcile.reports.claim_generator import ClaimGenerator
    try:
        claim = ClaimGenerator.generate_claim(str(db), body.shipment_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if claim.get("status") == "no_discrepancies":
        return claim

    from import_export.stock_reconcile.tracking.shipment_timeline import ShipmentTimeline
    ShipmentTimeline.add_event(db, body.shipment_id, "claim_generated",
        f"Claim generated — {claim.get('total_discrepancies', 0)} items")

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="stock-reconcile",
        summary=f"Claim generated for shipment #{body.shipment_id}",
        requires_human_action=True,
    )

    return claim


# ── Inventory ─────────────────────────────────────────────────────────────

@router.get("/api/inventory-summary")
async def inventory_summary(request: Request) -> list[dict]:
    db = request.app.state.db_paths["stock_reconcile"]

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT
                   COALESCE(ri.sku, ri.item_description) AS product_key,
                   ri.sku,
                   ri.item_description AS description,
                   ri.unit,
                   SUM(ri.quantity_received) AS total_quantity,
                   COUNT(DISTINCT wr.id) AS receipt_count,
                   MAX(wr.received_date) AS last_received,
                   SUM(CASE WHEN ri.condition = 'damaged' THEN ri.quantity_received ELSE 0 END) AS damaged_qty
               FROM receipt_items ri
               JOIN warehouse_receipts wr ON ri.receipt_id = wr.id
               JOIN shipments s ON wr.shipment_id = s.id
               WHERE s.status IN ('reconciled', 'closed')
               GROUP BY product_key
               ORDER BY total_quantity DESC"""
        ).fetchall()

    return [dict(r) for r in rows]


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/partials/manifest-upload", response_class=HTMLResponse)
async def manifest_upload_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["stock_reconcile"]
    with get_db(db) as conn:
        recent_shipments = conn.execute(
            "SELECT id, shipment_reference, bl_number, status, created_at FROM shipments ORDER BY created_at DESC LIMIT 10"
        ).fetchall()
    return templates.TemplateResponse(
        "stock_reconcile/partials/manifest_upload.html",
        {"request": request, "recent_shipments": [dict(r) for r in recent_shipments]},
    )


@router.get("/partials/receipt-matching", response_class=HTMLResponse)
async def receipt_matching_partial(request: Request, shipment_id: int | None = None) -> HTMLResponse:
    db = request.app.state.db_paths["stock_reconcile"]

    shipments: list[dict] = []
    manifest_items: list[dict] = []
    receipt_items: list[dict] = []
    results: list[dict] = []
    selected_shipment: dict | None = None

    with get_db(db) as conn:
        shipments = [dict(r) for r in conn.execute(
            "SELECT id, shipment_reference, bl_number, status FROM shipments ORDER BY created_at DESC"
        ).fetchall()]

        if shipment_id:
            selected_shipment = conn.execute(
                "SELECT * FROM shipments WHERE id = ?", (shipment_id,)
            ).fetchone()
            if selected_shipment:
                selected_shipment = dict(selected_shipment)

            manifest_items = [dict(r) for r in conn.execute(
                "SELECT * FROM manifest_items WHERE shipment_id = ?", (shipment_id,)
            ).fetchall()]

            receipt_rows = conn.execute(
                """SELECT ri.* FROM receipt_items ri
                   JOIN warehouse_receipts wr ON ri.receipt_id = wr.id
                   WHERE wr.shipment_id = ?""", (shipment_id,)
            ).fetchall()
            receipt_items = [dict(r) for r in receipt_rows]

            results = [dict(r) for r in conn.execute(
                "SELECT * FROM reconciliation_results WHERE shipment_id = ?", (shipment_id,)
            ).fetchall()]

    return templates.TemplateResponse(
        "stock_reconcile/partials/receipt_matching.html",
        {
            "request": request,
            "shipments": shipments,
            "selected_shipment": selected_shipment,
            "manifest_items": manifest_items,
            "receipt_items": receipt_items,
            "results": results,
            "shipment_id": shipment_id,
        },
    )


@router.get("/partials/discrepancy-report", response_class=HTMLResponse)
async def discrepancy_report_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["stock_reconcile"]

    from import_export.stock_reconcile.reconciliation.discrepancy_handler import DiscrepancyHandler
    discrepancies = DiscrepancyHandler.get_discrepancies(str(db))
    summary = DiscrepancyHandler.generate_discrepancy_summary(discrepancies)

    return templates.TemplateResponse(
        "stock_reconcile/partials/discrepancy_report.html",
        {"request": request, "discrepancies": discrepancies, "summary": summary},
    )
