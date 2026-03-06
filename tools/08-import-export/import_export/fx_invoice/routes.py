"""FXInvoice FastAPI routes — multi-currency invoicing, FX rates, payments."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/fx-invoice", tags=["FXInvoice"])

templates = Jinja2Templates(directory="import_export/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "fx-invoice",
        **extra,
    }


def _db(request: Request) -> str:
    return request.app.state.db_paths["fx_invoice"]


# ── Main page ──────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def fx_invoice_page(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        total_invoices = conn.execute("SELECT COUNT(*) FROM invoices").fetchone()[0]
        outstanding_row = conn.execute(
            """SELECT COALESCE(SUM(i.hkd_equivalent - COALESCE(
                   (SELECT SUM(p.hkd_equivalent) FROM payments p WHERE p.invoice_id = i.id), 0
               )), 0)
               FROM invoices i
               WHERE i.status IN ('sent','partially_paid','overdue')"""
        ).fetchone()
        outstanding_hkd = round(outstanding_row[0], 2) if outstanding_row else 0

        overdue_count = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'overdue' OR (status IN ('sent','partially_paid') AND due_date < date('now'))"
        ).fetchone()[0]

        fx_gl_row = conn.execute(
            """SELECT COALESCE(SUM(fx_gain_loss), 0) FROM payments
               WHERE payment_date >= date('now','start of month')"""
        ).fetchone()
        fx_gain_loss_mtd = round(fx_gl_row[0], 2) if fx_gl_row else 0

        currencies = conn.execute(
            "SELECT DISTINCT currency FROM invoices WHERE status != 'cancelled'"
        ).fetchall()
        active_currencies = [r[0] for r in currencies if r[0]]

        customers = [
            dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY company_name").fetchall()
        ]

    return templates.TemplateResponse(
        "fx_invoice/index.html",
        _ctx(
            request,
            total_invoices=total_invoices,
            outstanding_hkd=outstanding_hkd,
            overdue_count=overdue_count,
            fx_gain_loss_mtd=fx_gain_loss_mtd,
            active_currencies=active_currencies,
            customers=customers,
        ),
    )


# ── Customers ──────────────────────────────────────────────────────────────


@router.get("/api/customers")
async def list_customers(request: Request) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM customers ORDER BY company_name").fetchall()
    return [dict(r) for r in rows]


@router.post("/api/customers")
async def create_customer(request: Request) -> dict:
    db = _db(request)
    data = await request.json()
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO customers
               (company_name, contact_person, email, phone, address,
                default_currency, payment_terms_days, credit_limit, notes)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (
                data.get("company_name"),
                data.get("contact_person"),
                data.get("email"),
                data.get("phone"),
                data.get("address"),
                data.get("default_currency", "USD"),
                data.get("payment_terms_days", 30),
                data.get("credit_limit"),
                data.get("notes"),
            ),
        )
        customer_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-invoice",
        summary=f"Customer created: {data.get('company_name')} (#{customer_id})",
    )
    return {"id": customer_id, "company_name": data.get("company_name")}


# ── Invoices ───────────────────────────────────────────────────────────────


@router.get("/api/invoices")
async def list_invoices(
    request: Request, status: str | None = None
) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        if status:
            rows = conn.execute(
                """SELECT i.*, c.company_name as customer_name
                   FROM invoices i
                   LEFT JOIN customers c ON i.customer_id = c.id
                   WHERE i.status = ?
                   ORDER BY i.created_at DESC""",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT i.*, c.company_name as customer_name
                   FROM invoices i
                   LEFT JOIN customers c ON i.customer_id = c.id
                   ORDER BY i.created_at DESC"""
            ).fetchall()
    return [dict(r) for r in rows]


@router.post("/api/invoices")
async def create_invoice(request: Request) -> dict:
    db = _db(request)
    data = await request.json()

    from import_export.fx_invoice.invoicing.invoice_generator import InvoiceGenerator

    gen = InvoiceGenerator()
    result = gen.create_invoice(db, data)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-invoice",
        summary=f"Invoice {result['invoice_number']} created ({data.get('currency', 'HKD')} {result['total']:,.2f})",
    )
    return result


@router.get("/api/invoices/{invoice_id}")
async def get_invoice_detail(request: Request, invoice_id: int) -> dict:
    db = _db(request)
    with get_db(db) as conn:
        inv = conn.execute(
            """SELECT i.*, c.company_name as customer_name, c.address as customer_address,
                      c.contact_person, c.email as customer_email
               FROM invoices i
               LEFT JOIN customers c ON i.customer_id = c.id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")

        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY id",
                (invoice_id,),
            ).fetchall()
        ]

    invoice = dict(inv)
    invoice["items"] = items
    return invoice


@router.put("/api/invoices/{invoice_id}/status")
async def update_invoice_status(request: Request, invoice_id: int) -> dict:
    db = _db(request)
    data = await request.json()
    new_status = data.get("status")
    valid = {"draft", "sent", "partially_paid", "paid", "overdue", "cancelled"}
    if new_status not in valid:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid}")

    with get_db(db) as conn:
        conn.execute("UPDATE invoices SET status = ? WHERE id = ?", (new_status, invoice_id))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-invoice",
        summary=f"Invoice #{invoice_id} status → {new_status}",
    )
    return {"invoice_id": invoice_id, "status": new_status}


# ── PDF generation ─────────────────────────────────────────────────────────


@router.post("/api/invoices/{invoice_id}/pdf")
async def generate_invoice_pdf(request: Request, invoice_id: int) -> dict:
    db = _db(request)

    with get_db(db) as conn:
        inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,)).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        invoice = dict(inv)

        items = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ?", (invoice_id,)
            ).fetchall()
        ]

        bank_accounts = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM bank_accounts WHERE active = 1"
            ).fetchall()
        ]

    config = request.app.state.config
    company = {
        "company_name": config.extra.get("company_name", "Company"),
        "address": config.extra.get("company_address", ""),
        "br_number": config.extra.get("br_number", ""),
    }

    from import_export.fx_invoice.invoicing.template_engine import InvoiceTemplateEngine
    from import_export.fx_invoice.invoicing.pdf_export import PDFExporter

    engine = InvoiceTemplateEngine()
    html = engine.render_invoice_html(invoice, items, company, bank_accounts)

    workspace: Path = request.app.state.workspace
    pdf_dir = workspace / "invoices" / "pdf"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / f"{invoice['invoice_number']}.pdf"

    exporter = PDFExporter()
    pdf_bytes = exporter.generate_invoice_pdf(invoice, items, company, bank_accounts)
    pdf_path.write_bytes(pdf_bytes)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-invoice",
        summary=f"PDF generated for {invoice['invoice_number']}",
    )
    return {"invoice_id": invoice_id, "pdf_path": str(pdf_path)}


# ── Payments ───────────────────────────────────────────────────────────────


@router.get("/api/payments")
async def list_payments(request: Request, invoice_id: int | None = None) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        if invoice_id:
            rows = conn.execute(
                "SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date DESC",
                (invoice_id,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM payments ORDER BY payment_date DESC LIMIT 100"
            ).fetchall()
    return [dict(r) for r in rows]


@router.post("/api/payments")
async def record_payment(request: Request) -> dict:
    db = _db(request)
    data = await request.json()

    from import_export.fx_invoice.payments.payment_tracker import PaymentTracker

    tracker = PaymentTracker()
    result = tracker.record_payment(db, data)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-invoice",
        summary=(
            f"Payment recorded for invoice #{result['invoice_id']}: "
            f"{result['amount']:,.2f} (FX G/L: {result['fx_gain_loss']:+,.2f} HKD)"
        ),
        requires_human_action=abs(result["fx_gain_loss"]) > 1000,
    )
    return result


# ── FX Rates ───────────────────────────────────────────────────────────────


@router.get("/api/fx-rates")
async def get_fx_rates(request: Request) -> dict:
    db = _db(request)
    config = request.app.state.config
    monitored = config.extra.get("monitored_currencies", ["USD", "CNH", "EUR", "GBP", "JPY"])

    from import_export.fx_invoice.fx.rate_cache import RateCache
    from import_export.fx_invoice.fx.rate_fetcher import RateFetcher

    cache = RateCache(db)
    fetcher = RateFetcher()

    rates: dict[str, Any] = {}
    stale_currencies: list[str] = []

    for currency in monitored:
        cached = cache.get_latest_rate("HKD", currency)
        if cached and not cache.is_stale(cached):
            rates[currency] = {"rate": cached["rate"], "source": cached.get("source", "cache"), "fresh": True}
        else:
            stale_currencies.append(currency)

    if stale_currencies:
        fresh = fetcher.fetch_rates("HKD", stale_currencies)
        cache.cache_rates(fresh, fresh.get("source", "api"))
        for currency in stale_currencies:
            rate_val = fresh.get("rates", {}).get(currency)
            if rate_val is not None:
                rates[currency] = {"rate": rate_val, "source": fresh.get("source", "api"), "fresh": True}

    return {"base": "HKD", "rates": rates}


@router.get("/api/fx-rates/history")
async def get_fx_rate_history(
    request: Request,
    base: str = "HKD",
    target: str = "USD",
    days: int = 30,
) -> list[dict]:
    db = _db(request)
    from import_export.fx_invoice.fx.rate_cache import RateCache

    cache = RateCache(db)
    return cache.get_rate_history(base, target, days)


# ── Reports ────────────────────────────────────────────────────────────────


@router.get("/api/aging-report")
async def aging_report(request: Request) -> dict:
    db = _db(request)
    from import_export.fx_invoice.payments.aging_report import AgingReport

    report = AgingReport()
    return report.generate(db)


@router.get("/api/fx-summary")
async def fx_summary(request: Request) -> list[dict]:
    """Monthly FX gain/loss summary."""
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT
                   strftime('%Y-%m', payment_date) as month,
                   SUM(fx_gain_loss) as total_fx_gain_loss,
                   COUNT(*) as payment_count,
                   SUM(hkd_equivalent) as total_hkd
               FROM payments
               WHERE payment_date IS NOT NULL
               GROUP BY strftime('%Y-%m', payment_date)
               ORDER BY month DESC
               LIMIT 12"""
        ).fetchall()
    return [
        {
            "month": r["month"],
            "fx_gain_loss": round(r["total_fx_gain_loss"], 2),
            "payment_count": r["payment_count"],
            "total_hkd": round(r["total_hkd"], 2),
        }
        for r in rows
    ]


# ── Bank accounts ──────────────────────────────────────────────────────────


@router.get("/api/bank-accounts")
async def list_bank_accounts(request: Request) -> list[dict]:
    db = _db(request)
    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM bank_accounts WHERE active = 1 ORDER BY currency").fetchall()
    return [dict(r) for r in rows]


# ── Partials ───────────────────────────────────────────────────────────────


@router.get("/partials/invoice-builder", response_class=HTMLResponse)
async def invoice_builder_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        customers = [dict(r) for r in conn.execute("SELECT * FROM customers ORDER BY company_name").fetchall()]
    return templates.TemplateResponse(
        "fx_invoice/partials/invoice_builder.html",
        {"request": request, "customers": customers},
    )


@router.get("/partials/payment-tracker", response_class=HTMLResponse)
async def payment_tracker_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        invoices = [
            dict(r)
            for r in conn.execute(
                """SELECT i.*, c.company_name as customer_name
                   FROM invoices i
                   LEFT JOIN customers c ON i.customer_id = c.id
                   WHERE i.status IN ('sent','partially_paid','overdue')
                   ORDER BY i.due_date"""
            ).fetchall()
        ]
    return templates.TemplateResponse(
        "fx_invoice/partials/payment_tracker.html",
        {"request": request, "invoices": invoices},
    )
