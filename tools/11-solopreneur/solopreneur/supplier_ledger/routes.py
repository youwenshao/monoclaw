"""SupplierLedger FastAPI routes — payables/receivables for HK small businesses."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from solopreneur.supplier_ledger.ledger.invoice_manager import (
    create_invoice,
    get_invoices,
    get_outstanding_totals,
)
from solopreneur.supplier_ledger.ledger.payment_recorder import (
    get_recent_payments,
    record_payment,
)
from solopreneur.supplier_ledger.ledger.aging_engine import get_aging_summary
from solopreneur.supplier_ledger.ledger.reconciler import (
    auto_reconcile,
    import_bank_statement,
)
from solopreneur.supplier_ledger.forecasting.cash_flow import (
    forecast_cash_flow,
    get_cash_flow_summary,
)
from solopreneur.supplier_ledger.statements.statement_generator import (
    generate_monthly_statement,
)
from solopreneur.supplier_ledger.statements.pdf_builder import build_statement_pdf

router = APIRouter(prefix="/supplier-ledger", tags=["SupplierLedger"])

templates = Jinja2Templates(directory="solopreneur/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "supplier-ledger",
        **extra,
    }


# ── Main page ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def supplier_ledger_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]

    totals = get_outstanding_totals(db)
    cash_flow = get_cash_flow_summary(db)

    with get_db(db) as conn:
        overdue_count = conn.execute(
            "SELECT COUNT(*) FROM invoices WHERE status = 'overdue' OR "
            "(due_date < ? AND status NOT IN ('paid','written_off'))",
            (date.today().isoformat(),),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "supplier_ledger/index.html",
        _ctx(
            request,
            payables_total=totals["payables_total"],
            receivables_total=totals["receivables_total"],
            overdue_count=overdue_count,
            cash_flow_30d=cash_flow.get("30_day", {}).get("net", 0),
        ),
    )


# ── Partials ───────────────────────────────────────────────────────────────

@router.get("/partials/supplier-directory", response_class=HTMLResponse)
async def supplier_directory_partial(
    request: Request, q: str = "", contact_type: str = ""
) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]
    conditions: list[str] = ["c.active = 1"]
    params: list[Any] = []

    if q:
        conditions.append("(c.company_name LIKE ? OR c.company_name_tc LIKE ? OR c.contact_person LIKE ?)")
        like = f"%{q}%"
        params.extend([like, like, like])
    if contact_type:
        conditions.append("(c.contact_type = ? OR c.contact_type = 'both')")
        params.append(contact_type)

    where = "WHERE " + " AND ".join(conditions)

    with get_db(db) as conn:
        contacts = [
            dict(r) for r in conn.execute(
                f"""SELECT c.*,
                       COALESCE((SELECT SUM(balance) FROM invoices WHERE contact_id = c.id AND status NOT IN ('paid','written_off')), 0) as outstanding
                    FROM contacts c {where}
                    ORDER BY c.company_name""",
                params,
            ).fetchall()
        ]

    return templates.TemplateResponse(
        "supplier_ledger/partials/supplier_directory.html",
        {"request": request, "contacts": contacts},
    )


@router.get("/partials/aging-report", response_class=HTMLResponse)
async def aging_report_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]
    aging = get_aging_summary(db)
    return templates.TemplateResponse(
        "supplier_ledger/partials/aging_report.html",
        {"request": request, "aging": aging},
    )


@router.get("/partials/receivables-tracker", response_class=HTMLResponse)
async def receivables_tracker_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]
    invoices = get_invoices(db, invoice_type="receivable")
    return templates.TemplateResponse(
        "supplier_ledger/partials/receivables_tracker.html",
        {"request": request, "invoices": invoices},
    )


@router.get("/partials/cash-flow-forecast", response_class=HTMLResponse)
async def cash_flow_forecast_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]
    forecast = forecast_cash_flow(db, days_ahead=90)
    summary = get_cash_flow_summary(db)
    return templates.TemplateResponse(
        "supplier_ledger/partials/cash_flow_forecast.html",
        {"request": request, "forecast": forecast, "summary": summary},
    )


@router.get("/partials/transaction-log", response_class=HTMLResponse)
async def transaction_log_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["ledger"]
    payments = get_recent_payments(db, limit=100)
    return templates.TemplateResponse(
        "supplier_ledger/partials/transaction_log.html",
        {"request": request, "payments": payments},
    )


# ── Contacts ───────────────────────────────────────────────────────────────

class CreateContactRequest(BaseModel):
    contact_type: str
    company_name: str
    company_name_tc: str | None = None
    contact_person: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    address: str | None = None
    payment_terms_days: int = 30
    credit_limit: float | None = None
    br_number: str | None = None
    notes: str | None = None


@router.post("/contacts")
async def add_contact(request: Request, body: CreateContactRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["ledger"]

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO contacts
               (contact_type, company_name, company_name_tc, contact_person,
                phone, whatsapp, email, address, payment_terms_days,
                credit_limit, br_number, notes)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                body.contact_type, body.company_name, body.company_name_tc,
                body.contact_person, body.phone, body.whatsapp, body.email,
                body.address, body.payment_terms_days, body.credit_limit,
                body.br_number, body.notes,
            ),
        )
        contact_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-ledger",
        summary=f"New contact added: {body.company_name} ({body.contact_type})",
    )
    return {"contact_id": contact_id, "company_name": body.company_name}


# ── Invoices ───────────────────────────────────────────────────────────────

class CreateInvoiceRequest(BaseModel):
    contact_id: int
    invoice_type: str
    invoice_number: str | None = None
    invoice_date: str | None = None
    due_date: str | None = None
    currency: str = "HKD"
    total_amount: float
    notes: str | None = None
    pdf_path: str | None = None


@router.post("/invoices")
async def add_invoice(request: Request, body: CreateInvoiceRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["ledger"]
    inv = create_invoice(db, body.model_dump())

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-ledger",
        summary=f"Invoice {inv.get('invoice_number', inv['id'])} created — {body.invoice_type} HK${body.total_amount:,.2f}",
    )
    return inv


# ── Payments ───────────────────────────────────────────────────────────────

class RecordPaymentRequest(BaseModel):
    invoice_id: int
    amount: float
    payment_method: str
    cheque_number: str | None = None
    bank_reference: str | None = None
    notes: str | None = None


@router.post("/payments")
async def add_payment(request: Request, body: RecordPaymentRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["ledger"]
    pmt = record_payment(
        db,
        invoice_id=body.invoice_id,
        amount=body.amount,
        payment_method=body.payment_method,
        cheque_number=body.cheque_number,
        bank_reference=body.bank_reference,
        notes=body.notes,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-ledger",
        summary=f"Payment of HK${body.amount:,.2f} recorded ({body.payment_method})",
    )
    return pmt


# ── Bank import / reconcile ────────────────────────────────────────────────

@router.post("/bank-import")
async def bank_import(
    request: Request,
    file: UploadFile = File(...),
    bank_name: str = Form("HSBC"),
) -> dict[str, Any]:
    db = request.app.state.db_paths["ledger"]
    content = (await file.read()).decode("utf-8-sig")
    result = import_bank_statement(db, content, bank_name)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-ledger",
        summary=f"Bank statement imported: {result.get('imported_count', 0)} txns, {result.get('matched_count', 0)} matched",
    )
    return result


@router.post("/reconcile")
async def reconcile(request: Request) -> dict[str, Any]:
    db = request.app.state.db_paths["ledger"]
    result = auto_reconcile(db)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="supplier-ledger",
        summary=f"Reconciliation: {result['matched_count']} matched, {result['unmatched_count']} unmatched",
    )
    return result


# ── Statements ─────────────────────────────────────────────────────────────

@router.get("/statements/{contact_id}/{month}")
async def download_statement(
    request: Request, contact_id: int, month: str
) -> FileResponse:
    """Generate and download a PDF statement.  *month* format: ``YYYY-MM``."""
    db = request.app.state.db_paths["ledger"]
    try:
        year_i, month_i = (int(p) for p in month.split("-"))
    except ValueError:
        raise HTTPException(status_code=400, detail="Month must be YYYY-MM")

    stmt = generate_monthly_statement(db, contact_id, year_i, month_i)
    if "error" in stmt:
        raise HTTPException(status_code=404, detail=stmt["error"])

    workspace = request.app.state.workspace
    pdf_dir = workspace / "statements"
    pdf_path = pdf_dir / f"statement_{contact_id}_{month}.pdf"
    build_statement_pdf(stmt, pdf_path)

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"statement_{stmt['contact']['company_name']}_{month}.pdf",
    )
