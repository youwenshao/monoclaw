"""BizOwner OS FastAPI routes — Boss Mode dashboard for HK small businesses."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/biz-owner-os", tags=["BizOwnerOS"])

templates = Jinja2Templates(directory="solopreneur/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "biz-owner-os",
        **extra,
    }


def _db(request: Request) -> Path:
    return request.app.state.db_paths["bizowner"]


def _mona(request: Request) -> Path:
    return request.app.state.db_paths["mona_events"]


# ── Main page ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def biz_owner_os_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        today_rev = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS rev FROM sales WHERE DATE(sale_date) = DATE('now')"
        ).fetchone()["rev"]
        pending_msgs = conn.execute(
            "SELECT COUNT(*) FROM whatsapp_messages WHERE requires_followup = 1"
        ).fetchone()[0]

    from solopreneur.biz_owner_os.accounting.cash_flow import get_cash_position
    cash = get_cash_position(db)

    return templates.TemplateResponse(
        "biz_owner_os/index.html",
        _ctx(
            request,
            today_revenue=round(today_rev, 2),
            pending_messages=pending_msgs,
            cash_position=cash["cash_position"],
        ),
    )


# ── Boss Mode partial ─────────────────────────────────────────────────────

@router.get("/partials/boss-mode", response_class=HTMLResponse)
async def boss_mode_partial(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        today_rev = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS rev FROM sales WHERE DATE(sale_date) = DATE('now')"
        ).fetchone()["rev"]
        pending_msgs = conn.execute(
            "SELECT COUNT(*) FROM whatsapp_messages WHERE requires_followup = 1"
        ).fetchone()[0]

    from solopreneur.biz_owner_os.accounting.cash_flow import get_cash_position
    cash = get_cash_position(db)

    return templates.TemplateResponse(
        "biz_owner_os/partials/boss_mode.html",
        {
            "request": request,
            "today_revenue": round(today_rev, 2),
            "pending_messages": pending_msgs,
            "cash_position": cash["cash_position"],
        },
    )


# ── Revenue dashboard partial ─────────────────────────────────────────────

@router.get("/partials/revenue-dashboard", response_class=HTMLResponse)
async def revenue_dashboard_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today()
    month_start = today.replace(day=1)

    from solopreneur.biz_owner_os.pos.sales_aggregator import (
        get_revenue_by_payment_method,
        get_top_selling_items,
    )
    payment_breakdown = get_revenue_by_payment_method(db, month_start, today)
    top_items = get_top_selling_items(db, month_start, today, limit=10)

    with get_db(db) as conn:
        month_rev = conn.execute(
            "SELECT COALESCE(SUM(total_amount), 0) AS rev FROM sales WHERE DATE(sale_date) >= ?",
            (month_start.isoformat(),),
        ).fetchone()["rev"]

    return templates.TemplateResponse(
        "biz_owner_os/partials/revenue_dashboard.html",
        {
            "request": request,
            "payment_breakdown": payment_breakdown,
            "top_items": top_items,
            "month_revenue": round(month_rev, 2),
        },
    )


# ── WhatsApp inbox partial ────────────────────────────────────────────────

@router.get("/partials/whatsapp-inbox", response_class=HTMLResponse)
async def whatsapp_inbox_partial(
    request: Request, status: str | None = None
) -> HTMLResponse:
    from solopreneur.biz_owner_os.whatsapp.inbox_manager import get_inbox
    messages = get_inbox(_db(request), limit=30, status_filter=status)

    return templates.TemplateResponse(
        "biz_owner_os/partials/whatsapp_inbox.html",
        {"request": request, "messages": messages},
    )


# ── Inventory alerts partial ──────────────────────────────────────────────

@router.get("/partials/inventory-alerts", response_class=HTMLResponse)
async def inventory_alerts_partial(request: Request) -> HTMLResponse:
    from solopreneur.biz_owner_os.pos.inventory_tracker import get_low_stock_items, get_inventory_summary
    low_stock = get_low_stock_items(_db(request))
    summary = get_inventory_summary(_db(request))

    return templates.TemplateResponse(
        "biz_owner_os/partials/inventory_alerts.html",
        {
            "request": request,
            "low_stock_items": low_stock,
            "summary": summary,
        },
    )


# ── Customer CRM partial ──────────────────────────────────────────────────

@router.get("/partials/customer-crm", response_class=HTMLResponse)
async def customer_crm_partial(
    request: Request, search: str | None = None
) -> HTMLResponse:
    from solopreneur.biz_owner_os.crm.customer_database import get_customers
    from solopreneur.biz_owner_os.crm.engagement_tracker import get_customer_segments
    customers = get_customers(_db(request), search=search, limit=30)
    segments = get_customer_segments(_db(request))

    return templates.TemplateResponse(
        "biz_owner_os/partials/customer_crm.html",
        {
            "request": request,
            "customers": customers,
            "segments": segments,
        },
    )


# ── Record sale ────────────────────────────────────────────────────────────

class SaleRequest(BaseModel):
    total_amount: float
    payment_method: str = "cash"
    items: str = ""
    customer_phone: str = ""


@router.post("/sales")
async def record_sale(request: Request, body: SaleRequest) -> dict[str, Any]:
    from solopreneur.biz_owner_os.accounting.transaction_logger import record_income
    from solopreneur.biz_owner_os.crm.customer_database import merge_pos_customer

    sale_data = {
        "sale_date": date.today().isoformat(),
        "total_amount": body.total_amount,
        "payment_method": body.payment_method,
        "items": body.items,
        "customer_phone": body.customer_phone,
        "pos_source": "manual",
    }
    sale_id = record_income(_db(request), sale_data)

    if body.customer_phone:
        merge_pos_customer(_db(request), body.customer_phone, body.total_amount)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="biz-owner-os",
        summary=f"Sale recorded: HK${body.total_amount:,.2f} ({body.payment_method})",
    )

    return {"sale_id": sale_id, "status": "recorded"}


# ── Record expense ─────────────────────────────────────────────────────────

@router.post("/expenses")
async def record_expense(
    request: Request,
    description: str = Form(""),
    amount: float = Form(0),
    category: str = Form("other"),
    payment_method: str = Form("cash"),
    recurring: bool = Form(False),
    receipt: UploadFile | None = File(None),
) -> dict[str, Any]:
    from solopreneur.biz_owner_os.accounting.transaction_logger import record_expense as log_expense, save_receipt
    from solopreneur.biz_owner_os.accounting.categorizer import categorize_expense

    if category == "auto":
        llm = getattr(request.app.state, "llm", None)
        category = await categorize_expense(description, llm=llm)

    receipt_path = ""
    if receipt and receipt.filename:
        ext = Path(receipt.filename).suffix or ".jpg"
        file_bytes = await receipt.read()
        receipt_path = save_receipt(str(request.app.state.workspace), file_bytes, ext)

    expense_data = {
        "expense_date": date.today().isoformat(),
        "category": category,
        "description": description,
        "amount": amount,
        "receipt_photo": receipt_path,
        "payment_method": payment_method,
        "recurring": recurring,
    }
    expense_id = log_expense(_db(request), expense_data)

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="biz-owner-os",
        summary=f"Expense recorded: HK${amount:,.2f} ({category})",
    )

    return {"expense_id": expense_id, "category": category, "status": "recorded"}


# ── Twilio WhatsApp webhook ────────────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    form = await request.form()
    from_number = str(form.get("From", ""))
    message_body = str(form.get("Body", ""))

    phone = from_number.replace("whatsapp:", "").replace("+852", "").strip()

    from solopreneur.biz_owner_os.crm.customer_database import upsert_customer
    from solopreneur.biz_owner_os.whatsapp.inbox_manager import record_message
    from solopreneur.biz_owner_os.whatsapp.auto_responder import generate_response

    customer = upsert_customer(_db(request), phone)
    customer_id = customer["id"]

    record_message(_db(request), customer_id, "inbound", message_body, requires_followup=True)

    llm = getattr(request.app.state, "llm", None)
    reply = await generate_response(message_body, llm=llm)

    record_message(_db(request), customer_id, "outbound", reply)

    emit_event(
        _mona(request),
        event_type="info",
        tool_name="biz-owner-os",
        summary=f"WhatsApp message from {phone} auto-replied",
    )

    return {"status": "processed", "reply": reply}


# ── Broadcast ──────────────────────────────────────────────────────────────

class BroadcastRequest(BaseModel):
    message: str
    customer_tags: list[str] | None = None


@router.post("/broadcast")
async def send_broadcast(request: Request, body: BroadcastRequest) -> dict[str, Any]:
    from solopreneur.biz_owner_os.whatsapp.broadcast import send_broadcast as do_broadcast

    config = request.app.state.config
    twilio_client = None
    twilio_from = getattr(config.messaging, "twilio_whatsapp_from", "")

    if getattr(config.messaging, "twilio_account_sid", ""):
        try:
            from twilio.rest import Client
            twilio_client = Client(
                config.messaging.twilio_account_sid,
                config.messaging.twilio_auth_token,
            )
        except Exception:
            pass

    result = do_broadcast(
        _db(request),
        body.message,
        customer_tags=body.customer_tags,
        twilio_client=twilio_client,
        twilio_from=twilio_from,
    )

    emit_event(
        _mona(request),
        event_type="action_completed",
        tool_name="biz-owner-os",
        summary=f"Broadcast sent to {result['sent']} customers",
    )

    return result


# ── Analytics JSON endpoint ────────────────────────────────────────────────

@router.get("/analytics/revenue")
async def revenue_analytics(
    request: Request,
    period: str = "week",
) -> JSONResponse:
    """Revenue trend data for Chart.js consumption."""
    db = _db(request)
    today = date.today()

    if period == "month":
        start = today.replace(day=1)
    elif period == "year":
        start = today.replace(month=1, day=1)
    else:
        start = today - timedelta(days=6)

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT DATE(sale_date) AS day,
                      COALESCE(SUM(total_amount), 0) AS revenue
               FROM sales
               WHERE DATE(sale_date) BETWEEN ? AND ?
               GROUP BY DATE(sale_date)
               ORDER BY day""",
            (start.isoformat(), today.isoformat()),
        ).fetchall()

    labels = [dict(r)["day"] for r in rows]
    data = [dict(r)["revenue"] for r in rows]

    return JSONResponse({
        "labels": labels,
        "datasets": [{
            "label": "Revenue (HKD)",
            "data": data,
            "borderColor": "#d4a843",
            "backgroundColor": "rgba(212, 168, 67, 0.15)",
            "fill": True,
            "tension": 0.3,
        }],
    })
