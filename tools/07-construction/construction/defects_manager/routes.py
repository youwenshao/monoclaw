"""DefectsManager FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/defects-manager", tags=["DefectsManager"])
templates = Jinja2Templates(directory="construction/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "defects-manager", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["defects_manager"]


# -- Request models ------------------------------------------------------------

class DefectCreate(BaseModel):
    property_id: int
    unit: str = ""
    floor: str = ""
    location_detail: str = ""
    category: str = "other"
    description: str = ""
    reported_by: str = ""
    reported_phone: str = ""
    priority: str = "normal"


class DefectAssess(BaseModel):
    priority: str | None = None
    responsibility: str | None = None
    category: str | None = None


class WorkOrderCreate(BaseModel):
    defect_id: int
    contractor_id: int | None = None
    scope_of_work: str = ""
    estimated_cost: float | None = None
    target_completion: str | None = None


class ContractorCreate(BaseModel):
    company_name: str
    contact_person: str = ""
    phone: str = ""
    email: str = ""
    trades: str = "[]"
    registration_numbers: str = ""
    hourly_rate: float | None = None


# -- Page ----------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def defects_manager_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        properties = [dict(r) for r in conn.execute(
            "SELECT * FROM properties ORDER BY property_name"
        ).fetchall()]
        total_defects = conn.execute("SELECT COUNT(*) FROM defects").fetchone()[0]
        open_defects = conn.execute(
            "SELECT COUNT(*) FROM defects WHERE status NOT IN ('completed','closed')"
        ).fetchone()[0]
        emergency_count = conn.execute(
            "SELECT COUNT(*) FROM defects WHERE priority = 'emergency' AND status NOT IN ('completed','closed')"
        ).fetchone()[0]
        pending_wo = conn.execute(
            "SELECT COUNT(*) FROM work_orders WHERE status IN ('draft','issued')"
        ).fetchone()[0]
        recent_defects = [dict(r) for r in conn.execute(
            "SELECT d.*, p.property_name FROM defects d "
            "LEFT JOIN properties p ON d.property_id = p.id "
            "ORDER BY d.reported_date DESC LIMIT 20"
        ).fetchall()]

    return templates.TemplateResponse(
        "defects_manager/index.html",
        _ctx(
            request,
            properties=properties,
            total_defects=total_defects,
            open_defects=open_defects,
            emergency_count=emergency_count,
            pending_wo=pending_wo,
            recent_defects=recent_defects,
        ),
    )


# -- Defect CRUD ---------------------------------------------------------------

@router.post("/defects")
async def create_defect(request: Request, body: DefectCreate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO defects (property_id, unit, floor, location_detail, category, description, "
            "reported_by, reported_phone, priority) VALUES (?,?,?,?,?,?,?,?,?)",
            (body.property_id, body.unit, body.floor, body.location_detail, body.category,
             body.description, body.reported_by, body.reported_phone, body.priority),
        )
        defect_id = cursor.lastrowid

    from construction.defects_manager.defects.priority_engine import auto_escalate
    auto_escalate(_db(request), defect_id, body.category)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="defects-manager",
        summary=f"Defect #{defect_id} reported: {body.category} at {body.floor}/{body.unit}",
        requires_human_action=body.priority in ("emergency", "urgent"),
    )
    return {"defect_id": defect_id}


@router.get("/defects/{defect_id}")
async def get_defect(request: Request, defect_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT d.*, p.property_name FROM defects d "
            "LEFT JOIN properties p ON d.property_id = p.id WHERE d.id = ?",
            (defect_id,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Defect not found")
        updates = [dict(r) for r in conn.execute(
            "SELECT * FROM defect_updates WHERE defect_id = ? ORDER BY updated_at",
            (defect_id,),
        ).fetchall()]
        work_orders = [dict(r) for r in conn.execute(
            "SELECT wo.*, c.company_name AS contractor_name FROM work_orders wo "
            "LEFT JOIN contractors c ON wo.contractor_id = c.id WHERE wo.defect_id = ?",
            (defect_id,),
        ).fetchall()]
    return {**dict(row), "updates": updates, "work_orders": work_orders}


@router.post("/defects/{defect_id}/assess")
async def assess_defect(request: Request, defect_id: int, body: DefectAssess) -> dict[str, Any]:
    db = _db(request)
    updates: list[str] = []
    params: list[Any] = []
    if body.priority:
        updates.append("priority = ?")
        params.append(body.priority)
    if body.responsibility:
        updates.append("responsibility = ?")
        params.append(body.responsibility)
    if body.category:
        updates.append("category = ?")
        params.append(body.category)
    if not updates:
        return {"defect_id": defect_id, "updated": False}

    updates.append("status = 'assessed'")
    params.append(defect_id)

    with get_db(db) as conn:
        conn.execute(f"UPDATE defects SET {', '.join(updates)} WHERE id = ?", params)
        conn.execute(
            "INSERT INTO defect_updates (defect_id, update_type, description, updated_by) VALUES (?,?,?,?)",
            (defect_id, "assessment", f"Priority: {body.priority}, Responsibility: {body.responsibility}", "system"),
        )
    return {"defect_id": defect_id, "updated": True}


# -- Work Orders ---------------------------------------------------------------

@router.post("/work-orders")
async def create_work_order(request: Request, body: WorkOrderCreate) -> dict[str, Any]:
    db = _db(request)
    contractor_id = body.contractor_id

    if not contractor_id:
        from construction.defects_manager.work_orders.contractor_matcher import match_contractor
        with get_db(db) as conn:
            defect = conn.execute("SELECT category FROM defects WHERE id = ?", (body.defect_id,)).fetchone()
        if defect:
            contractor_id = match_contractor(db, defect["category"], request.app.state.config)

    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO work_orders (defect_id, contractor_id, scope_of_work, estimated_cost, "
            "issue_date, target_completion, status) VALUES (?,?,?,?,?,?,?)",
            (body.defect_id, contractor_id, body.scope_of_work, body.estimated_cost,
             date.today().isoformat(), body.target_completion, "draft"),
        )
        wo_id = cursor.lastrowid
        conn.execute("UPDATE defects SET status = 'work_ordered' WHERE id = ?", (body.defect_id,))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="defects-manager",
        summary=f"Work order #{wo_id} created for defect #{body.defect_id}",
    )
    return {"work_order_id": wo_id}


@router.post("/work-orders/{wo_id}/complete")
async def complete_work_order(
    request: Request,
    wo_id: int,
    sign_off_by: str = Form(""),
    photo: UploadFile | None = File(None),
) -> dict[str, Any]:
    db = _db(request)
    photo_path = None
    if photo and photo.filename:
        workspace: Path = request.app.state.workspace
        d = workspace / "photos" / "completions"
        d.mkdir(parents=True, exist_ok=True)
        photo_path = str(d / photo.filename)
        content = await photo.read()
        Path(photo_path).write_bytes(content)

    with get_db(db) as conn:
        conn.execute(
            "UPDATE work_orders SET status = 'completed', actual_completion = ?, sign_off_by = ?, "
            "sign_off_date = ?, completion_photos = COALESCE(?, completion_photos) WHERE id = ?",
            (date.today().isoformat(), sign_off_by, date.today().isoformat(),
             json.dumps([photo_path]) if photo_path else None, wo_id),
        )
        wo = conn.execute("SELECT defect_id FROM work_orders WHERE id = ?", (wo_id,)).fetchone()
        if wo:
            conn.execute("UPDATE defects SET status = 'completed', closed_date = ? WHERE id = ?",
                         (datetime.now().isoformat(), wo["defect_id"]))
    return {"work_order_id": wo_id, "status": "completed"}


# -- Contractors ---------------------------------------------------------------

@router.post("/contractors")
async def create_contractor(request: Request, body: ContractorCreate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO contractors (company_name, contact_person, phone, email, trades, "
            "registration_numbers, hourly_rate) VALUES (?,?,?,?,?,?,?)",
            (body.company_name, body.contact_person, body.phone, body.email,
             body.trades, body.registration_numbers, body.hourly_rate),
        )
    return {"contractor_id": cursor.lastrowid}


# -- WhatsApp webhook ----------------------------------------------------------

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    from construction.defects_manager.bot.whatsapp_handler import handle_incoming
    form = await request.form()
    await handle_incoming(dict(form), request.app.state)
    return {"status": "ok"}


# -- Partials ------------------------------------------------------------------

@router.get("/partials/defects", response_class=HTMLResponse)
async def defects_partial(request: Request, property_id: int | None = None, status: str | None = None) -> HTMLResponse:
    db = _db(request)
    query = (
        "SELECT d.*, p.property_name FROM defects d "
        "LEFT JOIN properties p ON d.property_id = p.id WHERE 1=1"
    )
    params: list[Any] = []
    if property_id:
        query += " AND d.property_id = ?"
        params.append(property_id)
    if status:
        query += " AND d.status = ?"
        params.append(status)
    query += " ORDER BY d.reported_date DESC LIMIT 50"

    with get_db(db) as conn:
        defects = [dict(r) for r in conn.execute(query, params).fetchall()]
    return templates.TemplateResponse(
        "defects_manager/partials/defect_log.html",
        {"request": request, "defects": defects},
    )


@router.get("/partials/work-orders", response_class=HTMLResponse)
async def work_orders_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        orders = [dict(r) for r in conn.execute(
            "SELECT wo.*, d.category, d.description AS defect_desc, c.company_name "
            "FROM work_orders wo "
            "LEFT JOIN defects d ON wo.defect_id = d.id "
            "LEFT JOIN contractors c ON wo.contractor_id = c.id "
            "ORDER BY wo.issue_date DESC LIMIT 20"
        ).fetchall()]
    return templates.TemplateResponse(
        "defects_manager/partials/work_order_form.html",
        {"request": request, "orders": orders},
    )


@router.get("/partials/contractors", response_class=HTMLResponse)
async def contractors_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        contractors = [dict(r) for r in conn.execute(
            "SELECT * FROM contractors WHERE active = TRUE ORDER BY company_name"
        ).fetchall()]
    return templates.TemplateResponse(
        "defects_manager/partials/defect_detail.html",
        {"request": request, "contractors": contractors},
    )


@router.get("/partials/analytics", response_class=HTMLResponse)
async def analytics_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        by_category = [dict(r) for r in conn.execute(
            "SELECT category, COUNT(*) as count FROM defects GROUP BY category ORDER BY count DESC"
        ).fetchall()]
        by_status = [dict(r) for r in conn.execute(
            "SELECT status, COUNT(*) as count FROM defects GROUP BY status"
        ).fetchall()]
        by_priority = [dict(r) for r in conn.execute(
            "SELECT priority, COUNT(*) as count FROM defects GROUP BY priority"
        ).fetchall()]
    return templates.TemplateResponse(
        "defects_manager/partials/analytics.html",
        {"request": request, "by_category": by_category, "by_status": by_status, "by_priority": by_priority},
    )


@router.get("/partials/dmc-matrix", response_class=HTMLResponse)
async def dmc_matrix_partial(request: Request) -> HTMLResponse:
    from construction.defects_manager.defects.dmc_resolver import get_default_matrix
    matrix = get_default_matrix()
    return templates.TemplateResponse(
        "defects_manager/partials/dmc_matrix.html",
        {"request": request, "matrix": matrix},
    )
