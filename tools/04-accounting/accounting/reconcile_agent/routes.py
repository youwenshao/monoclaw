"""ReconcileAgent FastAPI routes."""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/reconcile-agent", tags=["ReconcileAgent"])

templates = Jinja2Templates(directory="accounting/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "reconcile-agent", **extra}


def _uploads_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "reconcile" / "uploads"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _reports_dir(request: Request) -> Path:
    workspace: Path = request.app.state.workspace
    d = workspace / "reconcile" / "reports"
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def reconcile_agent_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        total_bank = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        total_ledger = conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
        matched_bank = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE match_status = 'matched'"
        ).fetchone()[0]
        unmatched_bank = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchone()[0]
        matched_ledger = conn.execute(
            "SELECT COUNT(*) FROM ledger_entries WHERE match_status = 'matched'"
        ).fetchone()[0]
        unmatched_ledger = conn.execute(
            "SELECT COUNT(*) FROM ledger_entries WHERE match_status = 'unmatched'"
        ).fetchone()[0]
        recent_reconciliations = [dict(r) for r in conn.execute(
            "SELECT * FROM reconciliations ORDER BY created_at DESC LIMIT 5"
        ).fetchall()]
        recent_bank = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions ORDER BY imported_at DESC LIMIT 20"
        ).fetchall()]
        recent_ledger = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries ORDER BY imported_at DESC LIMIT 20"
        ).fetchall()]

    return templates.TemplateResponse(
        "reconcile_agent/index.html",
        _ctx(
            request,
            total_bank=total_bank,
            total_ledger=total_ledger,
            matched_bank=matched_bank,
            unmatched_bank=unmatched_bank,
            matched_ledger=matched_ledger,
            unmatched_ledger=unmatched_ledger,
            recent_reconciliations=recent_reconciliations,
            recent_bank=recent_bank,
            recent_ledger=recent_ledger,
        ),
    )


# ── Upload bank statement ──────────────────────────────────────────────────

@router.post("/upload-statement")
async def upload_statement(
    request: Request,
    file: UploadFile = File(...),
    bank_name: str = Form(""),
) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]
    uploads = _uploads_dir(request)

    safe_name = f"{uuid.uuid4().hex}_{file.filename or 'statement'}"
    file_path = uploads / safe_name
    content = await file.read()
    file_path.write_bytes(content)

    from accounting.reconcile_agent.parsers.base import detect_parser, PARSER_REGISTRY

    # Ensure all parsers are registered
    from accounting.reconcile_agent.parsers import hsbc, hang_seng, boc, standard_chartered, virtual_banks, ofx_parser, pdf_parser  # noqa: F401

    parser = detect_parser(file_path)
    if parser is None and bank_name:
        bank_lower = bank_name.lower()
        for parser_cls in PARSER_REGISTRY:
            if bank_lower in parser_cls.bank_name.lower():
                parser = parser_cls()
                break

    if parser is None:
        raise HTTPException(status_code=400, detail="Could not detect statement format. Please specify bank_name.")

    try:
        result = parser.parse(file_path)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Failed to parse statement: {e}")

    batch_id = uuid.uuid4().hex[:12]
    inserted = 0

    with get_db(db) as conn:
        for txn in result.transactions:
            conn.execute(
                """INSERT INTO bank_transactions
                   (bank_name, transaction_date, value_date, description, reference,
                    debit, credit, balance, currency, transaction_type, import_batch)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (result.bank_name, txn.transaction_date.isoformat(),
                 txn.value_date.isoformat() if txn.value_date else None,
                 txn.description, txn.reference,
                 txn.debit, txn.credit, txn.balance,
                 txn.currency, txn.transaction_type, batch_id),
            )
            inserted += 1

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="reconcile-agent",
        summary=f"Bank statement uploaded: {result.bank_name}, {inserted} transactions (batch {batch_id})",
    )

    return {
        "bank_name": result.bank_name,
        "transactions_imported": inserted,
        "batch_id": batch_id,
        "currency": result.currency,
        "closing_balance": result.closing_balance,
        "warnings": result.warnings,
    }


# ── Upload ledger export ──────────────────────────────────────────────────

@router.post("/upload-ledger")
async def upload_ledger(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]

    content = await file.read()
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(text.splitlines())

    fieldnames = list(reader.fieldnames or [])
    norm_map = {f.strip().lower(): f for f in fieldnames}

    date_col = norm_map.get("date") or norm_map.get("entry_date") or norm_map.get("transaction date")
    desc_col = norm_map.get("description") or norm_map.get("details") or norm_map.get("memo")
    ref_col = norm_map.get("reference") or norm_map.get("ref")
    debit_col = norm_map.get("debit") or norm_map.get("dr")
    credit_col = norm_map.get("credit") or norm_map.get("cr")
    amount_col = norm_map.get("amount")
    acct_col = norm_map.get("account code") or norm_map.get("account") or norm_map.get("gl code")
    ccy_col = norm_map.get("currency") or norm_map.get("ccy")

    if not date_col:
        raise HTTPException(status_code=422, detail="Ledger CSV must have a date column")

    single_amount = amount_col is not None and debit_col is None
    batch_id = uuid.uuid4().hex[:12]
    inserted = 0

    with get_db(db) as conn:
        for row in reader:
            raw_date = row.get(date_col, "").strip()
            if not raw_date:
                continue

            try:
                entry_date = date.fromisoformat(raw_date)
            except ValueError:
                for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
                    try:
                        entry_date = datetime.strptime(raw_date, fmt).date()
                        break
                    except ValueError:
                        continue
                else:
                    continue

            description = row.get(desc_col or "", "").strip()
            reference = row.get(ref_col or "", "").strip() if ref_col else None
            account_code = row.get(acct_col or "", "").strip() if acct_col else None
            currency = row.get(ccy_col or "", "").strip().upper() if ccy_col else "HKD"
            if not currency:
                currency = "HKD"

            if single_amount:
                raw_amt = row.get(amount_col or "", "0").strip().replace(",", "")
                amount = float(raw_amt) if raw_amt else 0.0
                debit = abs(amount) if amount < 0 else 0.0
                credit = amount if amount > 0 else 0.0
            else:
                raw_dr = row.get(debit_col or "", "0").strip().replace(",", "")
                raw_cr = row.get(credit_col or "", "0").strip().replace(",", "")
                debit = float(raw_dr) if raw_dr else 0.0
                credit = float(raw_cr) if raw_cr else 0.0

            conn.execute(
                """INSERT INTO ledger_entries
                   (entry_date, description, reference, debit, credit,
                    currency, account_code, source)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (entry_date.isoformat(), description, reference,
                 debit, credit, currency, account_code, batch_id),
            )
            inserted += 1

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="reconcile-agent",
        summary=f"Ledger export uploaded: {inserted} entries (batch {batch_id})",
    )

    return {"entries_imported": inserted, "batch_id": batch_id}


# ── Auto-matching ──────────────────────────────────────────────────────────

@router.post("/match/{reconciliation_id}")
async def run_auto_match(request: Request, reconciliation_id: int | None = None) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]
    config = request.app.state.config

    with get_db(db) as conn:
        bank_txns = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchall()]
        ledger_entries = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries WHERE match_status = 'unmatched'"
        ).fetchall()]

    if not bank_txns and not ledger_entries:
        return {"message": "No unmatched entries to reconcile", "matched": 0}

    from accounting.reconcile_agent.matching.engine import run_matching

    match_config = {
        "date_tolerance_days": config.extra.get("date_tolerance_days", 3),
        "amount_tolerance": config.extra.get("amount_tolerance", 1.0),
        "fuzzy_match_threshold": config.extra.get("fuzzy_match_threshold", 80),
        "fx_rate_tolerance_pct": config.extra.get("fx_rate_tolerance_pct", 1.0),
    }

    result = run_matching(bank_txns, ledger_entries, match_config)

    with get_db(db) as conn:
        for m in result.matches:
            conn.execute(
                "UPDATE bank_transactions SET match_status = 'matched', matched_ledger_id = ? WHERE id = ?",
                (m.ledger_id, m.bank_id),
            )
            conn.execute(
                "UPDATE ledger_entries SET match_status = 'matched', matched_bank_id = ? WHERE id = ?",
                (m.bank_id, m.ledger_id),
            )

        for am in result.aggregate_matches:
            for bid in am.bank_ids:
                conn.execute(
                    "UPDATE bank_transactions SET match_status = 'matched', matched_ledger_id = ? WHERE id = ?",
                    (am.ledger_id, bid),
                )
            conn.execute(
                "UPDATE ledger_entries SET match_status = 'matched', matched_bank_id = ? WHERE id = ?",
                (am.bank_ids[0], am.ledger_id),
            )

        bank_closing = conn.execute(
            "SELECT balance FROM bank_transactions ORDER BY transaction_date DESC, id DESC LIMIT 1"
        ).fetchone()
        ledger_balance = conn.execute(
            "SELECT SUM(credit) - SUM(debit) FROM ledger_entries"
        ).fetchone()

        bank_bal = float(bank_closing[0]) if bank_closing and bank_closing[0] is not None else 0.0
        ledger_bal = float(ledger_balance[0]) if ledger_balance and ledger_balance[0] is not None else 0.0

        cursor = conn.execute(
            """INSERT INTO reconciliations
               (bank_closing_balance, ledger_closing_balance,
                matched_count, unmatched_bank, unmatched_ledger,
                difference, status)
               VALUES (?,?,?,?,?,?,?)""",
            (bank_bal, ledger_bal,
             result.stats["matched"],
             result.stats["unmatched_bank"],
             result.stats["unmatched_ledger"],
             round(bank_bal - ledger_bal, 2),
             "completed"),
        )
        rec_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="reconcile-agent",
        summary=(
            f"Auto-matching complete: {result.stats['matched']} matched, "
            f"{result.stats['unmatched_bank']} unmatched bank, "
            f"{result.stats['unmatched_ledger']} unmatched ledger"
        ),
        requires_human_action=result.stats["unmatched_bank"] > 0 or result.stats["unmatched_ledger"] > 0,
    )

    return {
        "reconciliation_id": rec_id,
        "stats": result.stats,
        "matches": [
            {"bank_id": m.bank_id, "ledger_id": m.ledger_id,
             "confidence": m.confidence, "strategy": m.strategy}
            for m in result.matches
        ],
    }


# ── Manual matching ────────────────────────────────────────────────────────

@router.post("/manual-match")
async def manual_match(
    request: Request,
    bank_id: int = Form(...),
    ledger_id: int = Form(...),
) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        bank_row = conn.execute(
            "SELECT * FROM bank_transactions WHERE id = ?", (bank_id,)
        ).fetchone()
        ledger_row = conn.execute(
            "SELECT * FROM ledger_entries WHERE id = ?", (ledger_id,)
        ).fetchone()

    if not bank_row:
        raise HTTPException(status_code=404, detail=f"Bank transaction {bank_id} not found")
    if not ledger_row:
        raise HTTPException(status_code=404, detail=f"Ledger entry {ledger_id} not found")

    with get_db(db) as conn:
        conn.execute(
            "UPDATE bank_transactions SET match_status = 'matched', matched_ledger_id = ? WHERE id = ?",
            (ledger_id, bank_id),
        )
        conn.execute(
            "UPDATE ledger_entries SET match_status = 'matched', matched_bank_id = ? WHERE id = ?",
            (bank_id, ledger_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="reconcile-agent",
        summary=f"Manual match: bank #{bank_id} ↔ ledger #{ledger_id}",
    )

    return {"status": "matched", "bank_id": bank_id, "ledger_id": ledger_id}


# ── Reconciliation history ────────────────────────────────────────────────

@router.get("/reconciliations")
async def list_reconciliations(request: Request) -> list[dict]:
    db = request.app.state.db_paths["reconcile_agent"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM reconciliations ORDER BY created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/reconciliations/{rec_id}")
async def reconciliation_detail(request: Request, rec_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM reconciliations WHERE id = ?", (rec_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    rec = dict(row)

    with get_db(db) as conn:
        matched_pairs = [dict(r) for r in conn.execute(
            """SELECT b.id as bank_id, b.description as bank_desc,
                      b.debit as bank_debit, b.credit as bank_credit,
                      b.transaction_date as bank_date,
                      l.id as ledger_id, l.description as ledger_desc,
                      l.debit as ledger_debit, l.credit as ledger_credit,
                      l.entry_date as ledger_date
               FROM bank_transactions b
               JOIN ledger_entries l ON b.matched_ledger_id = l.id
               WHERE b.match_status = 'matched'
               ORDER BY b.transaction_date DESC"""
        ).fetchall()]

        unmatched_bank = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched' ORDER BY transaction_date DESC"
        ).fetchall()]

        unmatched_ledger = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries WHERE match_status = 'unmatched' ORDER BY entry_date DESC"
        ).fetchall()]

    return {
        "reconciliation": rec,
        "matched_pairs": matched_pairs,
        "unmatched_bank": unmatched_bank,
        "unmatched_ledger": unmatched_ledger,
        "summary": {
            "matched_count": rec.get("matched_count", 0),
            "unmatched_bank": rec.get("unmatched_bank", 0),
            "unmatched_ledger": rec.get("unmatched_ledger", 0),
            "bank_closing": rec.get("bank_closing_balance"),
            "ledger_closing": rec.get("ledger_closing_balance"),
            "difference": rec.get("difference"),
        },
    }


# ── Report generation ──────────────────────────────────────────────────────

@router.get("/reconciliations/{rec_id}/report")
async def generate_report(
    request: Request,
    rec_id: int,
    format: str = "pdf",
) -> FileResponse:
    db = request.app.state.db_paths["reconcile_agent"]
    config = request.app.state.config

    with get_db(db) as conn:
        rec_row = conn.execute(
            "SELECT * FROM reconciliations WHERE id = ?", (rec_id,)
        ).fetchone()
    if not rec_row:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    rec = dict(rec_row)

    with get_db(db) as conn:
        unmatched_bank = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchall()]
        unmatched_ledger = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries WHERE match_status = 'unmatched'"
        ).fetchall()]

    from accounting.reconcile_agent.reporting.reconciliation import (
        build_reconciliation_statement,
        generate_excel_report,
        generate_pdf_report,
    )

    statement = build_reconciliation_statement(
        bank_balance=float(rec.get("bank_closing_balance") or 0),
        book_balance=float(rec.get("ledger_closing_balance") or 0),
        unmatched_bank=unmatched_bank,
        unmatched_ledger=unmatched_ledger,
        bank_name="HSBC",
        currency="HKD",
    )

    reports_dir = _reports_dir(request)
    firm_name = config.extra.get("firm_name", "")

    if format.lower() == "excel":
        output = generate_excel_report(statement, reports_dir, firm_name)
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    else:
        output = generate_pdf_report(statement, reports_dir, firm_name)
        media_type = "application/pdf"

    return FileResponse(path=str(output), filename=output.name, media_type=media_type)


# ── Discrepancies ──────────────────────────────────────────────────────────

@router.get("/discrepancies/{rec_id}")
async def get_discrepancies(request: Request, rec_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        rec_row = conn.execute(
            "SELECT * FROM reconciliations WHERE id = ?", (rec_id,)
        ).fetchone()
    if not rec_row:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    with get_db(db) as conn:
        unmatched_bank = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchall()]
        unmatched_ledger = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries WHERE match_status = 'unmatched'"
        ).fetchall()]

    from accounting.reconcile_agent.reporting.discrepancies import generate_discrepancy_report

    report = generate_discrepancy_report(
        unmatched_bank=unmatched_bank,
        unmatched_ledger=unmatched_ledger,
        reconciliation_id=rec_id,
    )

    return report.to_dict()


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/matching-review/partial", response_class=HTMLResponse)
async def matching_review_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        unmatched_bank = [dict(r) for r in conn.execute(
            "SELECT * FROM bank_transactions WHERE match_status = 'unmatched' ORDER BY transaction_date DESC LIMIT 30"
        ).fetchall()]
        unmatched_ledger = [dict(r) for r in conn.execute(
            "SELECT * FROM ledger_entries WHERE match_status = 'unmatched' ORDER BY entry_date DESC LIMIT 30"
        ).fetchall()]
        recent_matches = [dict(r) for r in conn.execute(
            """SELECT b.id as bank_id, b.description as bank_desc,
                      b.debit as bank_debit, b.credit as bank_credit,
                      l.id as ledger_id, l.description as ledger_desc,
                      l.debit as ledger_debit, l.credit as ledger_credit
               FROM bank_transactions b
               JOIN ledger_entries l ON b.matched_ledger_id = l.id
               WHERE b.match_status = 'matched'
               ORDER BY b.imported_at DESC LIMIT 20"""
        ).fetchall()]

    return templates.TemplateResponse(
        "reconcile_agent/partials/matching_review.html",
        {
            "request": request,
            "unmatched_bank": unmatched_bank,
            "unmatched_ledger": unmatched_ledger,
            "recent_matches": recent_matches,
        },
    )


@router.get("/summary/partial", response_class=HTMLResponse)
async def summary_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["reconcile_agent"]

    with get_db(db) as conn:
        total_bank = conn.execute("SELECT COUNT(*) FROM bank_transactions").fetchone()[0]
        total_ledger = conn.execute("SELECT COUNT(*) FROM ledger_entries").fetchone()[0]
        matched = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE match_status = 'matched'"
        ).fetchone()[0]
        unmatched_bank = conn.execute(
            "SELECT COUNT(*) FROM bank_transactions WHERE match_status = 'unmatched'"
        ).fetchone()[0]
        unmatched_ledger = conn.execute(
            "SELECT COUNT(*) FROM ledger_entries WHERE match_status = 'unmatched'"
        ).fetchone()[0]

        match_rate = round(matched / total_bank * 100, 1) if total_bank > 0 else 0.0

        last_rec = conn.execute(
            "SELECT * FROM reconciliations ORDER BY created_at DESC LIMIT 1"
        ).fetchone()

    return templates.TemplateResponse(
        "reconcile_agent/partials/summary.html",
        {
            "request": request,
            "total_bank": total_bank,
            "total_ledger": total_ledger,
            "matched": matched,
            "unmatched_bank": unmatched_bank,
            "unmatched_ledger": unmatched_ledger,
            "match_rate": match_rate,
            "last_reconciliation": dict(last_rec) if last_rec else None,
        },
    )
