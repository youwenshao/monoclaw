"""FXTracker FastAPI routes."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/fx-tracker", tags=["FXTracker"])

templates = Jinja2Templates(directory="accounting/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "fx-tracker", **extra}


def _db(request: Request):
    return request.app.state.db_paths["fx_tracker"]


# ── Dashboard page ─────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def fx_tracker_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        latest_rates = [dict(r) for r in conn.execute(
            """SELECT target_currency, mid_rate, date
               FROM exchange_rates
               WHERE date = (SELECT MAX(date) FROM exchange_rates)
               ORDER BY target_currency"""
        ).fetchall()]

        open_positions = [dict(r) for r in conn.execute(
            """SELECT id, currency, foreign_amount, hkd_amount, transaction_type, description
               FROM fx_transactions
               WHERE is_settled = 0
               ORDER BY transaction_date DESC"""
        ).fetchall()]

        total_unsettled = conn.execute(
            "SELECT COUNT(*) FROM fx_transactions WHERE is_settled = 0"
        ).fetchone()[0]

        total_realized = conn.execute(
            "SELECT COALESCE(SUM(realized_gain_loss), 0) FROM fx_transactions WHERE is_settled = 1"
        ).fetchone()[0]

    return templates.TemplateResponse(
        "fx_tracker/index.html",
        _ctx(
            request,
            latest_rates=latest_rates,
            open_positions=open_positions,
            total_unsettled=total_unsettled,
            total_realized=round(total_realized, 2),
        ),
    )


# ── Rate endpoints ─────────────────────────────────────────────────────────

@router.get("/rates")
async def get_rates(
    request: Request,
    currency: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    db = _db(request)
    clauses: list[str] = []
    params: list[Any] = []

    if currency:
        clauses.append("target_currency = ?")
        params.append(currency.upper())
    if start_date:
        clauses.append("date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("date <= ?")
        params.append(end_date)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_db(db) as conn:
        rows = conn.execute(
            f"SELECT * FROM exchange_rates{where} ORDER BY date DESC, target_currency",
            params,
        ).fetchall()

    return [dict(r) for r in rows]


@router.get("/rates/{currency}")
async def get_rate_history(
    request: Request,
    currency: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    db = _db(request)
    params: list[Any] = [currency.upper()]
    date_clause = ""

    if start_date:
        date_clause += " AND date >= ?"
        params.append(start_date)
    if end_date:
        date_clause += " AND date <= ?"
        params.append(end_date)

    with get_db(db) as conn:
        rows = conn.execute(
            f"SELECT * FROM exchange_rates WHERE target_currency = ?{date_clause} ORDER BY date",
            params,
        ).fetchall()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No rate history for {currency.upper()}")

    return [dict(r) for r in rows]


# ── Transaction endpoints ──────────────────────────────────────────────────

@router.post("/transactions")
async def create_transaction(request: Request) -> dict[str, Any]:
    body = await request.json()
    db = _db(request)

    required = ["transaction_date", "currency", "foreign_amount", "transaction_type"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    currency = body["currency"].upper()
    foreign_amount = float(body["foreign_amount"])
    exchange_rate = body.get("exchange_rate")

    if exchange_rate is None:
        from accounting.fx_tracker.rates.cache import get_rate
        exchange_rate = get_rate(
            date.fromisoformat(body["transaction_date"]),
            currency,
            db,
        )
        if exchange_rate is None:
            raise HTTPException(status_code=400, detail=f"No rate available for {currency} on {body['transaction_date']}; provide exchange_rate manually")
    else:
        exchange_rate = float(exchange_rate)

    hkd_amount = round(foreign_amount * exchange_rate, 2)

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO fx_transactions
               (transaction_date, description, currency, foreign_amount,
                exchange_rate, hkd_amount, transaction_type, nature, reference)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body["transaction_date"],
                body.get("description", ""),
                currency,
                foreign_amount,
                exchange_rate,
                hkd_amount,
                body["transaction_type"],
                body.get("nature", "revenue"),
                body.get("reference", ""),
            ),
        )
        tx_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-tracker",
        summary=f"FX transaction logged: {currency} {foreign_amount:,.2f} = HKD {hkd_amount:,.2f}",
    )

    return {
        "tx_id": tx_id,
        "currency": currency,
        "foreign_amount": foreign_amount,
        "exchange_rate": exchange_rate,
        "hkd_amount": hkd_amount,
    }


@router.get("/transactions")
async def list_transactions(
    request: Request,
    currency: str | None = None,
    settled: bool | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    db = _db(request)
    clauses: list[str] = []
    params: list[Any] = []

    if currency:
        clauses.append("currency = ?")
        params.append(currency.upper())
    if settled is not None:
        clauses.append("is_settled = ?")
        params.append(1 if settled else 0)
    if start_date:
        clauses.append("transaction_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("transaction_date <= ?")
        params.append(end_date)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    with get_db(db) as conn:
        rows = conn.execute(
            f"SELECT * FROM fx_transactions{where} ORDER BY transaction_date DESC",
            params,
        ).fetchall()

    return [dict(r) for r in rows]


# ── Settlement ─────────────────────────────────────────────────────────────

@router.post("/transactions/{tx_id}/settle")
async def settle_transaction(request: Request, tx_id: int) -> dict[str, Any]:
    body = await request.json()
    db = _db(request)

    settlement_rate = body.get("settlement_rate")
    settled_date = body.get("settled_date", date.today().isoformat())
    if settlement_rate is None:
        raise HTTPException(status_code=400, detail="settlement_rate is required")

    settlement_rate = float(settlement_rate)

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM fx_transactions WHERE id = ?", (tx_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Transaction not found")

        tx = dict(row)
        if tx["is_settled"]:
            raise HTTPException(status_code=400, detail="Transaction already settled")

    from accounting.fx_tracker.calculations.realized import calculate_realized_gain_loss

    result = calculate_realized_gain_loss(
        original_rate=tx["exchange_rate"],
        settlement_rate=settlement_rate,
        foreign_amount=tx["foreign_amount"],
        transaction_type=tx["transaction_type"],
    )

    settlement_hkd = round(tx["foreign_amount"] * settlement_rate, 2)

    with get_db(db) as conn:
        conn.execute(
            """UPDATE fx_transactions SET
                is_settled = 1, settled_date = ?, settlement_rate = ?,
                settlement_hkd = ?, realized_gain_loss = ?
               WHERE id = ?""",
            (settled_date, settlement_rate, settlement_hkd, result["gain_loss"], tx_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-tracker",
        summary=f"FX transaction #{tx_id} settled. Realized G/L: HKD {result['gain_loss']:,.2f}",
    )

    return {
        "tx_id": tx_id,
        "settlement_rate": settlement_rate,
        "settlement_hkd": settlement_hkd,
        "realized_gain_loss": result["gain_loss"],
        "settled_date": settled_date,
    }


# ── Revaluation ────────────────────────────────────────────────────────────

@router.post("/revalue")
async def revalue_positions(request: Request) -> dict[str, Any]:
    body = await request.json()
    period_end_date = body.get("period_end_date", date.today().isoformat())
    db = _db(request)

    from accounting.fx_tracker.calculations.unrealized import calculate_unrealized_gains

    results = calculate_unrealized_gains(period_end_date, db)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="fx-tracker",
        summary=f"Period-end revaluation at {period_end_date}: {len(results)} positions revalued",
    )

    return {
        "period_end_date": period_end_date,
        "revaluations": results,
        "total_unrealized": round(sum(r["unrealized_gain_loss"] for r in results), 2),
    }


# ── Gains & Losses report ─────────────────────────────────────────────────

@router.get("/gains-losses")
async def gains_losses_report(request: Request) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        realized = [dict(r) for r in conn.execute(
            """SELECT id, transaction_date, settled_date, currency, foreign_amount,
                      exchange_rate, settlement_rate, realized_gain_loss, nature
               FROM fx_transactions
               WHERE is_settled = 1 AND realized_gain_loss IS NOT NULL
               ORDER BY settled_date DESC"""
        ).fetchall()]

        unrealized = [dict(r) for r in conn.execute(
            """SELECT id, period_end_date, currency, outstanding_foreign_amount,
                      original_hkd_amount, closing_rate, revalued_hkd_amount,
                      unrealized_gain_loss
               FROM revaluations
               ORDER BY period_end_date DESC"""
        ).fetchall()]

    total_realized = sum(r["realized_gain_loss"] for r in realized)
    total_unrealized = sum(r["unrealized_gain_loss"] for r in unrealized)

    return {
        "realized": realized,
        "unrealized": unrealized,
        "total_realized": round(total_realized, 2),
        "total_unrealized": round(total_unrealized, 2),
        "net_fx_impact": round(total_realized + total_unrealized, 2),
    }


# ── Exposure ───────────────────────────────────────────────────────────────

@router.get("/exposure")
async def currency_exposure(request: Request) -> dict[str, Any]:
    db = _db(request)

    from accounting.fx_tracker.calculations.exposure import calculate_exposure

    exposure = calculate_exposure(db)
    return {"as_of": date.today().isoformat(), "exposure": exposure}


# ── Tax schedule ───────────────────────────────────────────────────────────

@router.get("/tax-schedule")
async def tax_schedule(request: Request) -> dict[str, Any]:
    db = _db(request)

    from accounting.fx_tracker.reporting.tax_schedule import generate_tax_schedule

    schedule = generate_tax_schedule(db)
    return schedule


# ── Rate alerts ────────────────────────────────────────────────────────────

@router.get("/alerts")
async def get_alerts(request: Request) -> list[dict[str, Any]]:
    db = _db(request)

    with get_db(db) as conn:
        rows = conn.execute("SELECT * FROM rate_alerts ORDER BY id").fetchall()

    return [dict(r) for r in rows]


@router.post("/alerts")
async def upsert_alert(request: Request) -> dict[str, Any]:
    body = await request.json()
    db = _db(request)

    required = ["currency_pair", "alert_type", "threshold"]
    for field in required:
        if field not in body:
            raise HTTPException(status_code=400, detail=f"Missing field: {field}")

    alert_id = body.get("id")

    with get_db(db) as conn:
        if alert_id:
            conn.execute(
                """UPDATE rate_alerts SET
                    currency_pair = ?, alert_type = ?, threshold = ?
                   WHERE id = ?""",
                (body["currency_pair"], body["alert_type"], float(body["threshold"]), alert_id),
            )
        else:
            cursor = conn.execute(
                """INSERT INTO rate_alerts (currency_pair, alert_type, threshold)
                   VALUES (?, ?, ?)""",
                (body["currency_pair"], body["alert_type"], float(body["threshold"])),
            )
            alert_id = cursor.lastrowid

    return {"alert_id": alert_id, "status": "saved"}


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/rates/partial", response_class=HTMLResponse)
async def rates_partial(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        rates = [dict(r) for r in conn.execute(
            """SELECT target_currency, mid_rate, buying_tt, selling_tt, date
               FROM exchange_rates
               WHERE date = (SELECT MAX(date) FROM exchange_rates)
               ORDER BY target_currency"""
        ).fetchall()]

    return templates.TemplateResponse(
        "fx_tracker/partials/rates_table.html",
        {"request": request, "rates": rates},
    )


@router.get("/exposure/partial", response_class=HTMLResponse)
async def exposure_partial(request: Request) -> HTMLResponse:
    db = _db(request)

    from accounting.fx_tracker.calculations.exposure import calculate_exposure

    exposure = calculate_exposure(db)

    return templates.TemplateResponse(
        "fx_tracker/partials/exposure_summary.html",
        {"request": request, "exposure": exposure},
    )
