"""SupplierBot FastAPI routes — supplier management, messaging, orders, pings."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/supplier-bot", tags=["SupplierBot"])

templates = Jinja2Templates(directory="import_export/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "supplier-bot", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def supplier_bot_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        supplier_count = conn.execute("SELECT COUNT(*) FROM suppliers WHERE active = 1").fetchone()[0]
        active_orders = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE production_status NOT IN ('delivered', 'completed')"
        ).fetchone()[0]
        unread_conversations = conn.execute(
            "SELECT COUNT(*) FROM conversations WHERE direction = 'inbound' AND extracted_data IS NULL"
        ).fetchone()[0]
        pending_pings = conn.execute(
            "SELECT COUNT(*) FROM status_pings WHERE sent_time IS NULL AND scheduled_time <= ?",
            (datetime.now().isoformat(),),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "supplier_bot/index.html",
        _ctx(
            request,
            supplier_count=supplier_count,
            active_orders=active_orders,
            unread_conversations=unread_conversations,
            pending_pings=pending_pings,
        ),
    )


# ── Suppliers ──────────────────────────────────────────────────────────────

@router.get("/api/suppliers")
async def list_suppliers(request: Request) -> list[dict]:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM suppliers ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


class CreateSupplierRequest(BaseModel):
    company_name_en: str | None = None
    company_name_cn: str
    factory_location: str | None = None
    contact_person: str | None = None
    wechat_id: str | None = None
    phone: str | None = None
    product_categories: list[str] | None = None
    payment_terms: str | None = None
    reliability_score: float = 5.0
    notes: str | None = None


@router.post("/api/suppliers")
async def create_supplier(request: Request, body: CreateSupplierRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]
    categories_json = json.dumps(body.product_categories) if body.product_categories else None

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO suppliers
               (company_name_en, company_name_cn, factory_location, contact_person,
                wechat_id, phone, product_categories, payment_terms, reliability_score, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (body.company_name_en, body.company_name_cn, body.factory_location,
             body.contact_person, body.wechat_id, body.phone, categories_json,
             body.payment_terms, body.reliability_score, body.notes),
        )
        supplier_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-bot",
        summary=f"New supplier added: {body.company_name_cn} ({body.company_name_en or 'N/A'})",
    )

    return {"supplier_id": supplier_id, "company_name_cn": body.company_name_cn}


@router.get("/api/suppliers/{supplier_id}")
async def get_supplier(request: Request, supplier_id: int) -> dict:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return dict(row)


class UpdateSupplierRequest(BaseModel):
    company_name_en: str | None = None
    company_name_cn: str | None = None
    factory_location: str | None = None
    contact_person: str | None = None
    wechat_id: str | None = None
    phone: str | None = None
    product_categories: list[str] | None = None
    payment_terms: str | None = None
    reliability_score: float | None = None
    notes: str | None = None
    active: bool | None = None


@router.put("/api/suppliers/{supplier_id}")
async def update_supplier(request: Request, supplier_id: int, body: UpdateSupplierRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        existing = conn.execute("SELECT * FROM suppliers WHERE id = ?", (supplier_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Supplier not found")

    updates: list[str] = []
    params: list[Any] = []
    for field, value in body.model_dump(exclude_unset=True).items():
        if field == "product_categories" and value is not None:
            value = json.dumps(value)
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        return {"supplier_id": supplier_id, "updated": False}

    params.append(supplier_id)
    with get_db(db) as conn:
        conn.execute(f"UPDATE suppliers SET {', '.join(updates)} WHERE id = ?", params)  # noqa: S608

    return {"supplier_id": supplier_id, "updated": True}


# ── Orders ─────────────────────────────────────────────────────────────────

@router.get("/api/orders")
async def list_orders(request: Request, supplier_id: int | None = None) -> list[dict]:
    db = request.app.state.db_paths["supplier_bot"]
    query = "SELECT o.*, s.company_name_cn, s.company_name_en FROM orders o LEFT JOIN suppliers s ON o.supplier_id = s.id"
    params: list[Any] = []
    if supplier_id is not None:
        query += " WHERE o.supplier_id = ?"
        params.append(supplier_id)
    query += " ORDER BY o.created_at DESC"
    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


class CreateOrderRequest(BaseModel):
    supplier_id: int
    order_reference: str
    product_description: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    currency: str = "USD"
    order_date: str | None = None
    expected_delivery: str | None = None
    payment_status: str = "pending_deposit"
    production_status: str = "not_started"
    notes: str | None = None


@router.post("/api/orders")
async def create_order(request: Request, body: CreateOrderRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (body.supplier_id,)).fetchone()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    order_date = body.order_date or datetime.now().strftime("%Y-%m-%d")
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO orders
               (supplier_id, order_reference, product_description, quantity,
                unit_price, currency, order_date, expected_delivery,
                payment_status, production_status, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (body.supplier_id, body.order_reference, body.product_description,
             body.quantity, body.unit_price, body.currency, order_date,
             body.expected_delivery, body.payment_status, body.production_status,
             body.notes),
        )
        order_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-bot",
        summary=f"Order {body.order_reference} created for supplier #{body.supplier_id}",
    )

    return {"order_id": order_id, "order_reference": body.order_reference}


class UpdateOrderRequest(BaseModel):
    product_description: str | None = None
    quantity: int | None = None
    unit_price: float | None = None
    currency: str | None = None
    expected_delivery: str | None = None
    actual_delivery: str | None = None
    payment_status: str | None = None
    production_status: str | None = None
    notes: str | None = None


@router.put("/api/orders/{order_id}")
async def update_order(request: Request, order_id: int, body: UpdateOrderRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        existing = conn.execute("SELECT * FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail="Order not found")

    updates: list[str] = []
    params: list[Any] = []
    for field, value in body.model_dump(exclude_unset=True).items():
        updates.append(f"{field} = ?")
        params.append(value)

    if not updates:
        return {"order_id": order_id, "updated": False}

    old_status = existing["production_status"]
    params.append(order_id)
    with get_db(db) as conn:
        conn.execute(f"UPDATE orders SET {', '.join(updates)} WHERE id = ?", params)  # noqa: S608

    if body.production_status and body.production_status != old_status:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="supplier-bot",
            summary=f"Order #{order_id} status: {old_status} → {body.production_status}",
        )

    return {"order_id": order_id, "updated": True}


# ── Conversations ──────────────────────────────────────────────────────────

@router.get("/api/conversations/{supplier_id}")
async def get_conversations(request: Request, supplier_id: int, limit: int = 100) -> list[dict]:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT * FROM conversations
               WHERE supplier_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (supplier_id, limit),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Messaging ──────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    supplier_id: int
    text: str
    translate: bool = False


@router.post("/api/send-message")
async def send_message(request: Request, body: SendMessageRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        supplier = conn.execute("SELECT * FROM suppliers WHERE id = ?", (body.supplier_id,)).fetchone()
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")

    translated_text: str | None = None
    original_lang = "en"

    if body.translate:
        from import_export.supplier_bot.translation.translator import Translator
        translator = Translator(llm=getattr(request.app.state, "llm", None))
        original_lang = translator.detect_language(body.text)
        target_lang = "zh" if original_lang == "en" else "en"
        translated_text = translator.translate(body.text, original_lang, target_lang)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO conversations
               (supplier_id, direction, original_text, translated_text,
                original_language, message_type, channel)
               VALUES (?,?,?,?,?,?,?)""",
            (body.supplier_id, "outbound", body.text, translated_text,
             original_lang, "text", "wechat"),
        )
        msg_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-bot",
        summary=f"Message sent to {dict(supplier)['company_name_cn']}",
    )

    return {
        "message_id": msg_id,
        "original_text": body.text,
        "translated_text": translated_text,
        "direction": "outbound",
    }


# ── Translation ────────────────────────────────────────────────────────────

class TranslateRequest(BaseModel):
    text: str
    source_lang: str = "en"
    target_lang: str = "zh"


@router.post("/api/translate")
async def translate_text(request: Request, body: TranslateRequest) -> dict[str, str]:
    from import_export.supplier_bot.translation.translator import Translator
    from import_export.supplier_bot.translation.terminology import TerminologyManager

    translator = Translator(llm=getattr(request.app.state, "llm", None))
    db = request.app.state.db_paths["supplier_bot"]

    term_mgr = TerminologyManager(db)
    glossary = term_mgr.get_glossary()

    text_with_terms = term_mgr.inject_terminology(body.text, glossary) if glossary else body.text
    translated = translator.translate(text_with_terms, body.source_lang, body.target_lang)

    return {
        "original": body.text,
        "translated": translated,
        "source_lang": body.source_lang,
        "target_lang": body.target_lang,
    }


# ── Pings ──────────────────────────────────────────────────────────────────

@router.get("/api/pings")
async def list_pings(request: Request) -> list[dict]:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT p.*, s.company_name_cn, s.company_name_en, o.order_reference
               FROM status_pings p
               LEFT JOIN suppliers s ON p.supplier_id = s.id
               LEFT JOIN orders o ON p.order_id = o.id
               ORDER BY p.scheduled_time DESC""",
        ).fetchall()
    return [dict(r) for r in rows]


class SchedulePingRequest(BaseModel):
    supplier_id: int
    order_id: int | None = None
    ping_type: str = "status_check"
    scheduled_time: str


@router.post("/api/pings")
async def schedule_ping(request: Request, body: SchedulePingRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["supplier_bot"]

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO status_pings (supplier_id, order_id, ping_type, scheduled_time)
               VALUES (?,?,?,?)""",
            (body.supplier_id, body.order_id, body.ping_type, body.scheduled_time),
        )
        ping_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="supplier-bot",
        summary=f"Ping scheduled for supplier #{body.supplier_id} at {body.scheduled_time}",
    )

    return {"ping_id": ping_id, "scheduled_time": body.scheduled_time}


# ── Partials ───────────────────────────────────────────────────────────────

@router.get("/partials/supplier-directory", response_class=HTMLResponse)
async def supplier_directory_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        suppliers = [dict(r) for r in conn.execute(
            "SELECT * FROM suppliers ORDER BY created_at DESC"
        ).fetchall()]
    return templates.TemplateResponse(
        "supplier_bot/partials/supplier_directory.html",
        {"request": request, "suppliers": suppliers},
    )


@router.get("/partials/order-board", response_class=HTMLResponse)
async def order_board_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["supplier_bot"]
    with get_db(db) as conn:
        orders = [dict(r) for r in conn.execute(
            """SELECT o.*, s.company_name_cn, s.company_name_en
               FROM orders o LEFT JOIN suppliers s ON o.supplier_id = s.id
               ORDER BY o.created_at DESC"""
        ).fetchall()]

    statuses = ["not_started", "in_production", "qc_pending", "qc_passed", "shipping", "delivered", "completed"]
    columns = {s: [o for o in orders if o["production_status"] == s] for s in statuses}

    return templates.TemplateResponse(
        "supplier_bot/partials/order_board.html",
        {"request": request, "columns": columns, "statuses": statuses},
    )
