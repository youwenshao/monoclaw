"""NoShowShield FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from fnb_hospitality.no_show_shield.scoring.reliability import (
    calculate_score,
    get_guest,
    list_guests,
    override_score,
)
from fnb_hospitality.no_show_shield.scoring.predictor import (
    predict_no_show,
    record_prediction,
)
from fnb_hospitality.no_show_shield.scoring.blacklist import (
    list_blacklisted,
    toggle_blacklist,
    requires_deposit,
)
from fnb_hospitality.no_show_shield.waitlist.manager import (
    add_to_waitlist,
    get_waitlist,
)
from fnb_hospitality.no_show_shield.waitlist.auto_fill import (
    attempt_auto_fill,
)

router = APIRouter(prefix="/no-show-shield", tags=["NoShowShield"])

templates = Jinja2Templates(directory="fnb_hospitality/dashboard/templates")


def _ctx(request: Request, active_tab: str = "no-show-shield", **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": active_tab,
        **extra,
    }


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["no_show_shield"])


# ── Pydantic models ────────────────────────────────────────────────────────


class ScoreOverrideRequest(BaseModel):
    score: str = Field(..., pattern=r"^[ABCD]$")
    reason: str = ""


class ConfirmationResponse(BaseModel):
    response: str = Field(..., pattern=r"^(confirmed|cancelled)$")
    channel: str = "whatsapp"


class WaitlistAddRequest(BaseModel):
    guest_name: str
    guest_phone: str = Field(..., pattern=r"^\+852[5679]\d{7}$")
    party_size: int = Field(..., ge=1, le=50)
    preferred_date: str
    preferred_time: str
    flexibility_minutes: int = 30


class WaitlistOfferRequest(BaseModel):
    date: str | None = None
    time: str | None = None
    party_size: int | None = None


# ── Main page ──────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def no_show_shield_page(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        pipeline = [dict(r) for r in conn.execute(
            """SELECT c.*, g.name as guest_name, g.reliability_score
               FROM confirmations c
               LEFT JOIN guests g ON g.phone = c.guest_phone
               WHERE DATE(c.sent_at) = ? OR c.status IN ('scheduled', 'sent')
               ORDER BY c.booking_id, c.step""",
            (today,),
        ).fetchall()]

        guests = [dict(r) for r in conn.execute(
            "SELECT * FROM guests ORDER BY total_bookings DESC LIMIT 20"
        ).fetchall()]

        waitlist_entries = [dict(r) for r in conn.execute(
            "SELECT * FROM waitlist WHERE status = 'waiting' ORDER BY created_at ASC"
        ).fetchall()]

        predictions = [dict(r) for r in conn.execute(
            """SELECT p.*, g.name as guest_name, g.reliability_score
               FROM no_show_predictions p
               LEFT JOIN guests g ON g.phone = (
                   SELECT guest_phone FROM confirmations
                   WHERE booking_id = p.booking_id LIMIT 1
               )
               WHERE DATE(p.predicted_at) = ?
               ORDER BY p.risk_score DESC""",
            (today,),
        ).fetchall()]

    score_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for g in guests:
        s = g.get("reliability_score", "B")
        if s in score_counts:
            score_counts[s] += 1

    return templates.TemplateResponse(
        "no_show_shield/index.html",
        _ctx(
            request,
            pipeline=pipeline,
            guests=guests,
            waitlist=waitlist_entries,
            predictions=predictions,
            score_counts=score_counts,
            today=today,
        ),
    )


# ── Guests ─────────────────────────────────────────────────────────────────


@router.get("/guests")
async def list_guests_route(
    request: Request,
    score: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    db = _db(request)
    return list_guests(db, score_filter=score, limit=limit)


@router.get("/guests/{phone}")
async def guest_detail(request: Request, phone: str) -> dict[str, Any]:
    db = _db(request)
    guest = get_guest(db, phone)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    with get_db(db) as conn:
        confirmations = [dict(r) for r in conn.execute(
            "SELECT * FROM confirmations WHERE guest_phone = ? ORDER BY sent_at DESC LIMIT 20",
            (phone,),
        ).fetchall()]

        predictions = [dict(r) for r in conn.execute(
            """SELECT * FROM no_show_predictions
               WHERE booking_id IN (
                   SELECT DISTINCT booking_id FROM confirmations WHERE guest_phone = ?
               )
               ORDER BY predicted_at DESC LIMIT 10""",
            (phone,),
        ).fetchall()]

    deposit_info = requires_deposit(db, phone)

    return {
        "guest": guest,
        "confirmations": confirmations,
        "predictions": predictions,
        "deposit_info": deposit_info,
        "current_score": calculate_score(db, phone),
    }


@router.post("/guests/{phone}/override-score")
async def override_guest_score(
    request: Request,
    phone: str,
    body: ScoreOverrideRequest,
) -> dict[str, Any]:
    db = _db(request)
    guest = get_guest(db, phone)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    old_score = guest["reliability_score"]
    success = override_score(db, phone, body.score, body.reason)

    if success:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="info",
            tool_name="no-show-shield",
            summary=f"Score override for {guest.get('name', phone)}: {old_score} → {body.score}",
            details=body.reason,
        )

    return {
        "phone": phone,
        "old_score": old_score,
        "new_score": body.score,
        "reason": body.reason,
        "success": success,
    }


# ── Confirmation pipeline ─────────────────────────────────────────────────


@router.get("/pipeline")
async def confirmation_pipeline(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT c.*, g.name as guest_name, g.reliability_score
               FROM confirmations c
               LEFT JOIN guests g ON g.phone = c.guest_phone
               WHERE DATE(c.sent_at) = ? OR c.status IN ('scheduled', 'sent')
               ORDER BY c.booking_id, c.step""",
            (today,),
        ).fetchall()

    return [dict(r) for r in rows]


@router.post("/confirmations/{booking_id}/respond")
async def process_confirmation_response(
    request: Request,
    booking_id: int,
    body: ConfirmationResponse,
) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            """SELECT * FROM confirmations
               WHERE booking_id = ? AND status = 'sent'
               ORDER BY step DESC LIMIT 1""",
            (booking_id,),
        ).fetchone()

    if not row:
        raise HTTPException(
            status_code=404,
            detail="No pending confirmation found for this booking",
        )

    confirmation = dict(row)

    with get_db(db) as conn:
        conn.execute(
            """UPDATE confirmations
               SET response = ?, responded_at = CURRENT_TIMESTAMP, status = ?
               WHERE id = ?""",
            (body.response, body.response, confirmation["id"]),
        )

        if body.response == "confirmed":
            conn.execute(
                """UPDATE confirmations
                   SET status = 'skipped'
                   WHERE booking_id = ? AND step > ? AND status IN ('scheduled', 'sent')""",
                (booking_id, confirmation["step"]),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="no-show-shield",
        summary=f"Booking #{booking_id} {body.response} by guest via {body.channel}",
    )

    return {
        "booking_id": booking_id,
        "response": body.response,
        "confirmation_id": confirmation["id"],
        "step": confirmation["step"],
    }


# ── Waitlist ───────────────────────────────────────────────────────────────


@router.get("/waitlist")
async def get_waitlist_route(
    request: Request,
    date_filter: str | None = None,
) -> list[dict[str, Any]]:
    db = _db(request)
    return get_waitlist(db, target_date=date_filter)


@router.post("/waitlist")
async def add_to_waitlist_route(
    request: Request,
    body: WaitlistAddRequest,
) -> dict[str, Any]:
    db = _db(request)
    entry_id = add_to_waitlist(
        db,
        guest_name=body.guest_name,
        guest_phone=body.guest_phone,
        party_size=body.party_size,
        preferred_date=body.preferred_date,
        preferred_time=body.preferred_time,
        flexibility_minutes=body.flexibility_minutes,
    )
    return {"id": entry_id, "status": "waiting"}


@router.post("/waitlist/{entry_id}/offer")
async def offer_to_waitlisted(
    request: Request,
    entry_id: int,
    body: WaitlistOfferRequest | None = None,
) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM waitlist WHERE id = ?", (entry_id,)
        ).fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Waitlist entry not found")

    entry = dict(row)
    offer_date = (body.date if body and body.date else entry["preferred_date"])
    offer_time = (body.time if body and body.time else entry["preferred_time"])
    offer_size = (body.party_size if body and body.party_size else entry["party_size"])

    from fnb_hospitality.no_show_shield.confirmation.messenger import Messenger

    config = request.app.state.config
    messenger = Messenger(
        twilio_account_sid=config.messaging.twilio_account_sid,
        twilio_auth_token=config.messaging.twilio_auth_token,
        twilio_whatsapp_from=config.messaging.twilio_whatsapp_from,
        default_language=config.messaging.default_language,
        restaurant_name=config.extra.get("restaurant_name", ""),
    )

    messenger.send_waitlist_offer(
        phone=entry["guest_phone"],
        date=offer_date,
        time=offer_time,
        party_size=offer_size,
    )

    with get_db(db) as conn:
        conn.execute(
            "UPDATE waitlist SET status = 'offered' WHERE id = ?", (entry_id,)
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="no-show-shield",
        summary=f"Manual waitlist offer sent to {entry.get('guest_name', entry['guest_phone'])}",
    )

    return {"entry_id": entry_id, "status": "offered", "offered_to": entry["guest_phone"]}


# ── Predictions ────────────────────────────────────────────────────────────


@router.get("/predictions/today")
async def today_predictions(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        rows = conn.execute(
            """SELECT p.*, g.name as guest_name, g.phone as guest_phone
               FROM no_show_predictions p
               LEFT JOIN guests g ON g.phone = (
                   SELECT guest_phone FROM confirmations
                   WHERE booking_id = p.booking_id LIMIT 1
               )
               WHERE DATE(p.predicted_at) = ?
               ORDER BY p.risk_score DESC""",
            (today,),
        ).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        if d.get("risk_factors") and isinstance(d["risk_factors"], str):
            try:
                d["risk_factors"] = json.loads(d["risk_factors"])
            except (json.JSONDecodeError, TypeError):
                pass
        results.append(d)

    return results


# ── Blacklist ──────────────────────────────────────────────────────────────


@router.get("/blacklist")
async def get_blacklist(request: Request) -> list[dict[str, Any]]:
    db = _db(request)
    return list_blacklisted(db)


@router.post("/blacklist/{phone}/toggle")
async def toggle_blacklist_route(
    request: Request,
    phone: str,
) -> dict[str, Any]:
    db = _db(request)
    result = toggle_blacklist(db, phone)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


# ── HTMX partials ─────────────────────────────────────────────────────────


@router.get("/partials/pipeline", response_class=HTMLResponse)
async def partial_pipeline(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        pipeline = [dict(r) for r in conn.execute(
            """SELECT c.*, g.name as guest_name, g.reliability_score
               FROM confirmations c
               LEFT JOIN guests g ON g.phone = c.guest_phone
               WHERE DATE(c.sent_at) = ? OR c.status IN ('scheduled', 'sent')
               ORDER BY c.booking_id, c.step""",
            (today,),
        ).fetchall()]

    return templates.TemplateResponse(
        "no_show_shield/partials/pipeline.html",
        {"request": request, "pipeline": pipeline},
    )


@router.get("/partials/reliability-cards", response_class=HTMLResponse)
async def partial_reliability_cards(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        guests = [dict(r) for r in conn.execute(
            "SELECT * FROM guests ORDER BY total_bookings DESC LIMIT 20"
        ).fetchall()]

    score_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for g in guests:
        s = g.get("reliability_score", "B")
        if s in score_counts:
            score_counts[s] += 1

    return templates.TemplateResponse(
        "no_show_shield/partials/reliability_cards.html",
        {"request": request, "guests": guests, "score_counts": score_counts},
    )


@router.get("/partials/waitlist", response_class=HTMLResponse)
async def partial_waitlist(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        waitlist_entries = [dict(r) for r in conn.execute(
            "SELECT * FROM waitlist WHERE status = 'waiting' ORDER BY created_at ASC"
        ).fetchall()]

    return templates.TemplateResponse(
        "no_show_shield/partials/waitlist.html",
        {"request": request, "waitlist": waitlist_entries},
    )


@router.get("/partials/predictions", response_class=HTMLResponse)
async def partial_predictions(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        predictions = [dict(r) for r in conn.execute(
            """SELECT p.*, g.name as guest_name, g.reliability_score
               FROM no_show_predictions p
               LEFT JOIN guests g ON g.phone = (
                   SELECT guest_phone FROM confirmations
                   WHERE booking_id = p.booking_id LIMIT 1
               )
               WHERE DATE(p.predicted_at) = ?
               ORDER BY p.risk_score DESC""",
            (today,),
        ).fetchall()]

    for p in predictions:
        if p.get("risk_factors") and isinstance(p["risk_factors"], str):
            try:
                p["risk_factors"] = json.loads(p["risk_factors"])
            except (json.JSONDecodeError, TypeError):
                pass

    return templates.TemplateResponse(
        "no_show_shield/partials/predictions.html",
        {"request": request, "predictions": predictions},
    )
