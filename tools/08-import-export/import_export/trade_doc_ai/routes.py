"""TradeDoc AI FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/trade-doc-ai", tags=["TradeDocAI"])

templates = Jinja2Templates(directory="import_export/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "trade-doc-ai", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def trade_doc_ai_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["trade_doc_ai"]

    with get_db(db) as conn:
        products_count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]

        declarations_filed = conn.execute(
            "SELECT COUNT(*) FROM trade_declarations WHERE filing_status IN ('filed','accepted')"
        ).fetchone()[0]
        declarations_pending = conn.execute(
            "SELECT COUNT(*) FROM trade_declarations WHERE filing_status = 'draft'"
        ).fetchone()[0]

        strategic_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE is_strategic = 1"
        ).fetchone()[0]

        deadline_alerts = conn.execute(
            """SELECT COUNT(*) FROM trade_declarations
               WHERE filing_status = 'draft'
                 AND filing_deadline IS NOT NULL
                 AND filing_deadline <= date('now', '+3 days')"""
        ).fetchone()[0]

    return templates.TemplateResponse(
        "trade_doc_ai/index.html",
        _ctx(
            request,
            products_count=products_count,
            declarations_filed=declarations_filed,
            declarations_pending=declarations_pending,
            strategic_count=strategic_count,
            deadline_alerts=deadline_alerts,
        ),
    )


# ── HS Classification API ─────────────────────────────────────────────────

class ClassifyRequest(BaseModel):
    description: str


@router.post("/api/classify")
async def classify_hs(request: Request, body: ClassifyRequest) -> list[dict]:
    db = request.app.state.db_paths["trade_doc_ai"]
    llm = getattr(request.app.state, "llm", None)

    from import_export.trade_doc_ai.classification.hs_classifier import HSClassifier
    classifier = HSClassifier(db)
    suggestions = classifier.classify(body.description, llm=llm)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="trade-doc-ai",
        summary=f"HS classification: \"{body.description[:60]}\" → {len(suggestions)} suggestions",
    )

    return suggestions


# ── Products API ──────────────────────────────────────────────────────────

@router.get("/api/products")
async def list_products(request: Request) -> list[dict]:
    db = request.app.state.db_paths["trade_doc_ai"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM products ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


class ProductCreate(BaseModel):
    description_en: str
    description_tc: str | None = None
    hs_code: str | None = None
    hs_description: str | None = None
    is_strategic: bool = False
    strategic_category: str | None = None
    is_dutiable: bool = False
    unit_of_measurement: str | None = None
    typical_origin: str | None = None


@router.post("/api/products")
async def create_product(request: Request, body: ProductCreate) -> dict[str, Any]:
    db = request.app.state.db_paths["trade_doc_ai"]
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO products
               (description_en, description_tc, hs_code, hs_description,
                is_strategic, strategic_category, is_dutiable,
                unit_of_measurement, typical_origin)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (body.description_en, body.description_tc, body.hs_code,
             body.hs_description, body.is_strategic, body.strategic_category,
             body.is_dutiable, body.unit_of_measurement, body.typical_origin),
        )
        product_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="trade-doc-ai",
        summary=f"Product created: {body.description_en}",
    )

    return {"product_id": product_id, "status": "created"}


# ── Declarations API ──────────────────────────────────────────────────────

@router.get("/api/declarations")
async def list_declarations(request: Request) -> list[dict]:
    db = request.app.state.db_paths["trade_doc_ai"]
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT td.*,
                      (SELECT COUNT(*) FROM declaration_items WHERE declaration_id = td.id) AS item_count
               FROM trade_declarations td
               ORDER BY td.created_at DESC"""
        ).fetchall()
    return [dict(r) for r in rows]


# ── TDEC API ──────────────────────────────────────────────────────────────

class TDECRequest(BaseModel):
    declaration_type: str
    shipper: str
    consignee: str
    country_of_origin: str | None = None
    country_of_destination: str | None = None
    transport_mode: str = "sea"
    vessel_flight: str | None = None
    currency: str = "HKD"
    items: list[dict] = []


@router.post("/api/tdec")
async def create_tdec(request: Request, body: TDECRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["trade_doc_ai"]

    from import_export.trade_doc_ai.documents.tdec_generator import TDECGenerator
    generator = TDECGenerator()

    form_data = generator.generate(body.model_dump())

    ref_number = _next_reference(db, body.declaration_type)
    total_value = form_data.get("total_value", 0)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO trade_declarations
               (declaration_type, reference_number, shipper, consignee,
                country_of_origin, country_of_destination, transport_mode,
                vessel_flight, total_value, currency, filing_status, filing_deadline)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (body.declaration_type, ref_number, body.shipper, body.consignee,
             body.country_of_origin, body.country_of_destination,
             body.transport_mode, body.vessel_flight, total_value,
             body.currency, "draft", form_data["filing_deadline"]),
        )
        decl_id = cursor.lastrowid

        for item in form_data.get("items", []):
            conn.execute(
                """INSERT INTO declaration_items
                   (declaration_id, hs_code, quantity, unit, value, currency,
                    country_of_origin, description)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (decl_id, item["hs_code"], item["quantity"], item["unit"],
                 item["value"], item.get("currency", body.currency),
                 item.get("country_of_origin", ""), item["description"]),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="trade-doc-ai",
        summary=f"TDEC created: {ref_number} ({body.declaration_type})",
    )

    return {
        "declaration_id": decl_id,
        "reference_number": ref_number,
        "filing_deadline": form_data["filing_deadline"],
        "form_data": form_data,
    }


# ── Invoice API ───────────────────────────────────────────────────────────

class InvoiceRequest(BaseModel):
    invoice_number: str | None = None
    invoice_date: str | None = None
    currency: str = "USD"
    incoterms: str = "FOB"
    incoterms_location: str = ""
    seller: dict = {}
    buyer: dict = {}
    items: list[dict] = []
    freight: float = 0
    insurance: float = 0
    discount: float = 0
    country_of_origin: str = ""
    transport_mode: str = "Sea"
    terms: str = ""


@router.post("/api/invoice")
async def generate_invoice(request: Request, body: InvoiceRequest) -> dict[str, Any]:
    from import_export.trade_doc_ai.documents.invoice_generator import CommercialInvoiceGenerator
    gen = CommercialInvoiceGenerator()

    data = body.model_dump()
    if not data.get("invoice_number"):
        data["invoice_number"] = f"INV-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    if not data.get("invoice_date"):
        data["invoice_date"] = date.today().isoformat()

    invoice = gen.generate(data)
    html = gen.to_html(invoice)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="trade-doc-ai",
        summary=f"Invoice generated: {invoice['invoice_number']}",
    )

    return {"invoice": invoice, "html": html}


# ── Certificate of Origin API ─────────────────────────────────────────────

class CORequest(BaseModel):
    co_type: str = "general"
    exporter: dict = {}
    consignee: dict = {}
    products: list[dict] = []
    declaration_id: int | None = None
    currency: str = "HKD"
    transport_mode: str = "sea"
    vessel_flight: str = ""
    port_of_loading: str = "Hong Kong"
    port_of_discharge: str = ""
    departure_date: str = ""
    factory_registration: str = ""
    hk_value_added_pct: float = 0
    declared_rvc_pct: float = 0


@router.post("/api/co")
async def create_co(request: Request, body: CORequest) -> dict[str, Any]:
    db = request.app.state.db_paths["trade_doc_ai"]

    from import_export.trade_doc_ai.documents.co_generator import COGenerator
    gen = COGenerator()
    application = gen.generate(body.model_dump())

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO certificates_of_origin
               (declaration_id, co_type, status)
               VALUES (?,?,?)""",
            (body.declaration_id, body.co_type, "draft"),
        )
        co_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="trade-doc-ai",
        summary=f"CO application created (type={body.co_type})",
    )

    return {"co_id": co_id, "application": application}


# ── Strategic Screening API ───────────────────────────────────────────────

class ScreenRequest(BaseModel):
    description: str
    hs_code: str | None = None


@router.post("/api/screen")
async def strategic_screen(request: Request, body: ScreenRequest) -> dict:
    from import_export.trade_doc_ai.classification.strategic_screener import StrategicScreener
    screener = StrategicScreener()
    result = screener.screen(body.description, hs_code=body.hs_code)

    if result["is_strategic"]:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="alert",
            tool_name="trade-doc-ai",
            summary=f"Strategic commodity detected: {body.description[:60]}",
            details=result.get("details", ""),
            requires_human_action=True,
        )

    return result


# ── Filing Status API ─────────────────────────────────────────────────────

@router.get("/api/filing-status")
async def filing_status_list(request: Request) -> dict[str, Any]:
    db = request.app.state.db_paths["trade_doc_ai"]

    from import_export.trade_doc_ai.filing.filing_tracker import FilingTracker
    tracker = FilingTracker()

    return {
        "pending": tracker.get_pending_filings(db),
        "overdue": tracker.get_overdue_filings(db),
        "all": tracker.get_all_filings(db),
    }


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/partials/hs-classifier", response_class=HTMLResponse)
async def hs_classifier_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "trade_doc_ai/partials/hs_classifier.html",
        {"request": request},
    )


@router.get("/partials/filing-tracker", response_class=HTMLResponse)
async def filing_tracker_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["trade_doc_ai"]

    from import_export.trade_doc_ai.filing.filing_tracker import FilingTracker
    tracker = FilingTracker()
    filings = tracker.get_all_filings(db)

    return templates.TemplateResponse(
        "trade_doc_ai/partials/filing_tracker.html",
        {"request": request, "filings": filings},
    )


@router.get("/partials/tdec-form", response_class=HTMLResponse)
async def tdec_form_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "trade_doc_ai/partials/tdec_form.html",
        {"request": request},
    )


@router.get("/partials/invoice-builder", response_class=HTMLResponse)
async def invoice_builder_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "trade_doc_ai/partials/invoice_builder.html",
        {"request": request},
    )


@router.get("/partials/co-form", response_class=HTMLResponse)
async def co_form_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "trade_doc_ai/partials/co_form.html",
        {"request": request},
    )


@router.get("/partials/strategic-alert", response_class=HTMLResponse)
async def strategic_alert_partial(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "trade_doc_ai/partials/strategic_alert.html",
        {"request": request},
    )


# ── Helpers ───────────────────────────────────────────────────────────────

def _next_reference(db_path, declaration_type: str) -> str:
    """Generate the next TDEC reference number."""
    prefix_map = {"import": "IM", "export": "EX", "re_export": "RE"}
    prefix = prefix_map.get(declaration_type, "XX")
    year = datetime.now().year

    with get_db(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM trade_declarations WHERE reference_number LIKE ?",
            (f"TDEC-{year}-{prefix}-%",),
        ).fetchone()
        seq = (row[0] if row else 0) + 1

    return f"TDEC-{year}-{prefix}-{seq:03d}"
