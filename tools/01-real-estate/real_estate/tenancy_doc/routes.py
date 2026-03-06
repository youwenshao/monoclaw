"""TenancyDoc FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from real_estate.tenancy_doc.generators.cr109 import generate_cr109
from real_estate.tenancy_doc.generators.hkid import validate_hkid
from real_estate.tenancy_doc.generators.inventory import generate_inventory_checklist
from real_estate.tenancy_doc.generators.stamp_duty import calculate_stamp_duty
from real_estate.tenancy_doc.generators.tenancy_agreement import generate_tenancy_agreement
from real_estate.tenancy_doc.tracking.renewals import (
    create_renewal_alerts,
    get_overdue_cr109,
    get_upcoming_renewals,
)

router = APIRouter(prefix="/tenancy-doc", tags=["TenancyDoc"])

templates = Jinja2Templates(directory="real_estate/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "tenancy-doc", **extra}


def _docs_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "documents" / "tenancy"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def tenancy_doc_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["tenancy_doc"]
    today = date.today().isoformat()

    with get_db(db) as conn:
        tenancies = [dict(r) for r in conn.execute(
            "SELECT * FROM tenancies ORDER BY created_at DESC"
        ).fetchall()]
        active = conn.execute(
            "SELECT COUNT(*) FROM tenancies WHERE status = 'active' AND end_date >= ?",
            (today,),
        ).fetchone()[0]

    upcoming = get_upcoming_renewals(db, days_ahead=90)
    overdue = get_overdue_cr109(db)

    return templates.TemplateResponse(
        "tenancy_doc/index.html",
        _ctx(
            request,
            tenancies=tenancies,
            active_tenancies_count=active,
            pending_renewals_count=len(upcoming),
            overdue_cr109_count=len(overdue),
            upcoming_renewals=upcoming,
            upcoming_renewals_json=json.dumps(upcoming),
        ),
    )


# ── Create tenancy + agreement ─────────────────────────────────────────────

class CreateTenancyRequest(BaseModel):
    property_address: str
    property_address_zh: str | None = None
    district: str | None = None
    landlord_name: str
    landlord_hkid: str | None = None
    landlord_phone: str | None = None
    tenant_name: str
    tenant_hkid: str | None = None
    tenant_phone: str | None = None
    monthly_rent: int
    deposit_amount: int | None = None
    term_months: int
    start_date: str
    end_date: str
    break_clause_date: str | None = None
    special_conditions: list[str] | None = None

    @field_validator("landlord_hkid", "tenant_hkid")
    @classmethod
    def validate_hkid_format(cls, v: str | None) -> str | None:
        if v and not validate_hkid(v):
            raise ValueError(f"Invalid HKID: {v}")
        return v


@router.post("/agreements")
async def create_agreement(request: Request, body: CreateTenancyRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["tenancy_doc"]
    data = body.model_dump()

    if data.get("deposit_amount") is None:
        data["deposit_amount"] = data["monthly_rent"] * 2

    duty = calculate_stamp_duty(data["monthly_rent"], data["term_months"])
    data["stamp_duty_amount"] = duty["duty_amount"]

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO tenancies
               (property_address, property_address_zh, district,
                landlord_name, landlord_hkid, landlord_phone,
                tenant_name, tenant_hkid, tenant_phone,
                monthly_rent, deposit_amount, term_months,
                start_date, end_date, break_clause_date, stamp_duty_amount)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                data["property_address"], data.get("property_address_zh"),
                data.get("district"),
                data["landlord_name"], data.get("landlord_hkid"),
                data.get("landlord_phone"),
                data["tenant_name"], data.get("tenant_hkid"),
                data.get("tenant_phone"),
                data["monthly_rent"], data["deposit_amount"],
                data["term_months"], data["start_date"], data["end_date"],
                data.get("break_clause_date"), data["stamp_duty_amount"],
            ),
        )
        tenancy_id = cursor.lastrowid

    data["id"] = tenancy_id
    doc_path = generate_tenancy_agreement(data, _docs_dir(request))

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO documents (tenancy_id, doc_type, file_path)
               VALUES (?, 'tenancy_agreement', ?)""",
            (tenancy_id, str(doc_path)),
        )

    create_renewal_alerts(db, tenancy_id)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tenancy-doc",
        summary=f"Tenancy #{tenancy_id} created with agreement — {data['property_address']}",
        details=f"Tenant: {data['tenant_name']}, Rent: HK${data['monthly_rent']:,}/month",
    )

    return {
        "tenancy_id": tenancy_id,
        "document_path": str(doc_path),
        "stamp_duty": duty,
    }


# ── Stamp duty calculator ─────────────────────────────────────────────────

@router.get("/stamp-duty/calculate")
async def stamp_duty_calc(
    request: Request,
    monthly_rent: int,
    term_months: int,
) -> dict[str, Any]:
    config = request.app.state.config
    rates = config.extra.get("stamp_duty_rates")
    return calculate_stamp_duty(monthly_rent, term_months, rates=rates)


@router.get("/stamp-duty/partial", response_class=HTMLResponse)
async def stamp_duty_partial(
    request: Request,
    monthly_rent: int = 0,
    term_months: int = 0,
) -> HTMLResponse:
    config = request.app.state.config
    rates = getattr(config, "extra", {}).get("stamp_duty_rates")
    result = calculate_stamp_duty(monthly_rent, term_months, rates=rates)
    return templates.TemplateResponse(
        "tenancy_doc/partials/stamp_duty_result.html",
        {"request": request, "monthly_rent": monthly_rent, "term_months": term_months, "result": result},
    )


# ── CR109 ──────────────────────────────────────────────────────────────────

class CR109Request(BaseModel):
    tenancy_id: int


@router.post("/cr109")
async def generate_cr109_form(request: Request, body: CR109Request) -> dict[str, Any]:
    db = request.app.state.db_paths["tenancy_doc"]
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM tenancies WHERE id = ?", (body.tenancy_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Tenancy not found")

    tenancy = dict(row)
    doc_path = generate_cr109(tenancy, _docs_dir(request))

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO documents (tenancy_id, doc_type, file_path)
               VALUES (?, 'cr109', ?)""",
            (body.tenancy_id, str(doc_path)),
        )
        conn.execute(
            "UPDATE tenancies SET cr109_filed = 1, cr109_filed_date = ? WHERE id = ?",
            (date.today().isoformat(), body.tenancy_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tenancy-doc",
        summary=f"CR109 generated for tenancy #{body.tenancy_id}",
    )

    return {
        "tenancy_id": body.tenancy_id,
        "document_path": str(doc_path),
    }


# ── Inventory ──────────────────────────────────────────────────────────────

class InventoryRequest(BaseModel):
    tenancy_id: int
    rooms: list[dict[str, Any]] | None = None


@router.post("/inventory")
async def generate_inventory(request: Request, body: InventoryRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["tenancy_doc"]
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM tenancies WHERE id = ?", (body.tenancy_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Tenancy not found")

    tenancy = dict(row)
    rooms = body.rooms or []
    doc_path = generate_inventory_checklist(tenancy, rooms, _docs_dir(request))

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO documents (tenancy_id, doc_type, file_path)
               VALUES (?, 'inventory', ?)""",
            (body.tenancy_id, str(doc_path)),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="tenancy-doc",
        summary=f"Inventory checklist generated for tenancy #{body.tenancy_id}",
    )

    return {
        "tenancy_id": body.tenancy_id,
        "document_path": str(doc_path),
    }


# ── Renewals ───────────────────────────────────────────────────────────────

@router.get("/renewals")
async def renewals(request: Request, days_ahead: int = 90) -> dict[str, Any]:
    db = request.app.state.db_paths["tenancy_doc"]
    upcoming = get_upcoming_renewals(db, days_ahead=days_ahead)
    overdue_cr109 = get_overdue_cr109(db)
    return {
        "upcoming_renewals": upcoming,
        "overdue_cr109": overdue_cr109,
        "days_ahead": days_ahead,
    }


# ── Documents ──────────────────────────────────────────────────────────────

@router.get("/documents/partial", response_class=HTMLResponse)
async def documents_partial(
    request: Request,
    tenancy_id: int | None = None,
    doc_type: str | None = None,
) -> HTMLResponse:
    if doc_type == "":
        doc_type = None
    db = request.app.state.db_paths["tenancy_doc"]
    query = "SELECT * FROM documents WHERE 1=1"
    params: list[Any] = []

    if tenancy_id is not None:
        query += " AND tenancy_id = ?"
        params.append(tenancy_id)
    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)

    query += " ORDER BY generated_at DESC"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    documents = [dict(r) for r in rows]
    return templates.TemplateResponse(
        "tenancy_doc/partials/documents_table.html",
        {"request": request, "documents": documents},
    )


@router.get("/documents")
async def list_documents(
    request: Request,
    tenancy_id: int | None = None,
    doc_type: str | None = None,
) -> list[dict]:
    db = request.app.state.db_paths["tenancy_doc"]
    query = "SELECT * FROM documents WHERE 1=1"
    params: list[Any] = []

    if tenancy_id is not None:
        query += " AND tenancy_id = ?"
        params.append(tenancy_id)
    if doc_type:
        query += " AND doc_type = ?"
        params.append(doc_type)

    query += " ORDER BY generated_at DESC"

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/documents/{doc_id}/download")
async def download_document(request: Request, doc_id: int) -> FileResponse:
    db = request.app.state.db_paths["tenancy_doc"]
    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = dict(row)
    file_path = Path(doc["file_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    media_type = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if file_path.suffix == ".docx"
        else "application/pdf"
    )
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type=media_type,
    )
