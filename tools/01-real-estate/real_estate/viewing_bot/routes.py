"""ViewingBot FastAPI routes — automated property viewing coordinator."""

from __future__ import annotations

import logging
import re
from datetime import datetime, date, timedelta
from typing import Any

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel

from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from real_estate.viewing_bot.messaging.parser import parse_viewing_request, build_fallback_form_response
from real_estate.viewing_bot.messaging.templates import render_message
from real_estate.viewing_bot.scheduling.slots import get_available_slots
from real_estate.viewing_bot.scheduling.conflict import detect_conflicts
from real_estate.viewing_bot.scheduling.optimizer import optimize_route, HK_DISTRICT_COORDS
from real_estate.viewing_bot.scheduling.weather import get_weather_warnings, is_viewing_unsafe, auto_cancel_unsafe_viewings

router = APIRouter(prefix="/viewing-bot", tags=["ViewingBot"])

templates = Jinja2Templates(directory="real_estate/dashboard/templates")

logger = logging.getLogger("openclaw.viewing_bot.routes")

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "viewing-bot", **extra}


def _db(request: Request) -> str:
    return request.app.state.db_paths["viewing_bot"]


def _mona_db(request: Request) -> str:
    return request.app.state.db_paths["mona_events"]


# ── Page ──────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def viewing_bot_page(request: Request) -> HTMLResponse:
    """Render the main viewing bot dashboard with today's viewings."""
    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        viewings = [dict(r) for r in conn.execute(
            """SELECT * FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) = ?
               ORDER BY COALESCE(confirmed_datetime, proposed_datetime)""",
            (today,),
        ).fetchall()]

        today_count = len(viewings)
        confirmed_count = sum(1 for v in viewings if v.get("status") == "confirmed")
        pending_count = sum(1 for v in viewings if v.get("status") == "pending")

        follow_ups_row = conn.execute(
            """SELECT COUNT(*) as n FROM follow_ups f
               JOIN viewings v ON v.id = f.viewing_id
               WHERE f.next_action IS NOT NULL AND f.next_action != ''""",
        ).fetchone()
        follow_ups_due = follow_ups_row["n"] if follow_ups_row else 0

    return templates.TemplateResponse(
        "viewing_bot/index.html",
        _ctx(
            request,
            viewings=viewings,
            today=today,
            today_count=today_count,
            confirmed_count=confirmed_count,
            pending_count=pending_count,
            follow_ups_due=follow_ups_due,
        ),
    )


# ── Twilio WhatsApp Webhook ──────────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> PlainTextResponse:
    """Handle incoming Twilio WhatsApp messages.

    Parses intent via LLM, then creates/updates viewings accordingly.
    Returns TwiML-compatible plain text response.
    """
    form = await request.form()
    data = dict(form)
    sender = (data.get("From", "") or "").replace("whatsapp:", "")
    body = data.get("Body", "") or ""

    if not body.strip():
        return PlainTextResponse("")

    llm = request.app.state.llm
    parsed = await parse_viewing_request(llm, body)
    config = request.app.state.config
    language = config.messaging.default_language

    _log_message(_db(request), direction="in", phone=sender, text=body, viewing_id=None)

    reply = ""
    intent = parsed["intent"]

    if intent == "book_viewing":
        reply = await _handle_book(request, sender, parsed, language)
    elif intent == "confirm":
        reply = await _handle_confirm_from_chat(request, sender, language)
    elif intent == "cancel":
        reply = await _handle_cancel_from_chat(request, sender, parsed, language)
    elif intent == "reschedule":
        reply = await _handle_reschedule_from_chat(request, sender, parsed, language)
    elif intent == "check_availability":
        reply = _handle_availability(request, parsed, language)
    else:
        reply = build_fallback_form_response(language)

    _log_message(_db(request), direction="out", phone=sender, text=reply, viewing_id=None)

    return PlainTextResponse(reply)


async def _handle_book(request: Request, sender: str, parsed: dict, language: str) -> str:
    proposed_dt = parsed.get("preferred_datetime")
    if not proposed_dt:
        if language == "zh":
            return "請提供你想睇樓嘅日期同時間。"
        return "Please provide your preferred date and time for the viewing."

    if isinstance(proposed_dt, str):
        try:
            proposed_dt = datetime.fromisoformat(proposed_dt)
        except ValueError:
            return "Sorry, I couldn't parse that date/time. Please use format: YYYY-MM-DD HH:MM"

    property_ref = parsed.get("property_ref") or "UNKNOWN"
    viewer_name = parsed.get("viewer_name") or ""
    party_size = parsed.get("party_size") or 1
    notes = parsed.get("notes") or ""

    config = request.app.state.config
    agent_phone = config.messaging.twilio_whatsapp_from

    conflicts = detect_conflicts(_db(request), proposed_dt, agent_phone, district="")
    if any(c["severity"] == "error" for c in conflicts):
        detail = conflicts[0]["detail"]
        if language == "zh":
            return f"呢個時間有衝突：{detail}\n請建議其他時間。"
        return f"There's a scheduling conflict: {detail}\nPlease suggest another time."

    with get_db(_db(request)) as conn:
        cursor = conn.execute(
            """INSERT INTO viewings
               (property_ref, viewer_name, viewer_phone, agent_phone,
                proposed_datetime, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending')""",
            (property_ref, viewer_name, sender, agent_phone,
             proposed_dt.isoformat(), notes),
        )
        viewing_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="viewing-bot",
        summary=f"New viewing #{viewing_id} booked: {property_ref}",
    )

    return render_message("confirmation", {
        "property_ref": property_ref,
        "property_address": "",
        "datetime": proposed_dt,
        "viewer_name": viewer_name,
        "party_size": party_size,
    }, language)


async def _handle_confirm_from_chat(request: Request, sender: str, language: str) -> str:
    with get_db(_db(request)) as conn:
        row = conn.execute(
            """SELECT id, property_ref FROM viewings
               WHERE viewer_phone = ? AND status = 'pending'
               ORDER BY created_at DESC LIMIT 1""",
            (sender,),
        ).fetchone()
        if not row:
            return "No pending viewing found." if language == "en" else "搵唔到待確認嘅睇樓。"
        conn.execute(
            "UPDATE viewings SET viewer_confirmed = 1, status = 'confirmed' WHERE id = ?",
            (row["id"],),
        )
    return render_message("confirmation", {
        "property_ref": row["property_ref"],
        "property_address": "",
        "datetime": "",
        "viewer_name": "",
        "party_size": 1,
    }, language)


async def _handle_cancel_from_chat(request: Request, sender: str, parsed: dict, language: str) -> str:
    reason = parsed.get("notes") or "Cancelled via WhatsApp"
    with get_db(_db(request)) as conn:
        row = conn.execute(
            """SELECT id, property_ref, proposed_datetime FROM viewings
               WHERE viewer_phone = ? AND status IN ('pending', 'confirmed')
               ORDER BY created_at DESC LIMIT 1""",
            (sender,),
        ).fetchone()
        if not row:
            return "No active viewing found to cancel." if language == "en" else "搵唔到可以取消嘅睇樓。"
        conn.execute(
            "UPDATE viewings SET status = 'cancelled', notes = COALESCE(notes || '\\n', '') || ? WHERE id = ?",
            (reason, row["id"]),
        )
    return render_message("cancellation", {
        "property_ref": row["property_ref"],
        "datetime": row["proposed_datetime"],
        "reason": reason,
    }, language)


async def _handle_reschedule_from_chat(request: Request, sender: str, parsed: dict, language: str) -> str:
    new_dt = parsed.get("preferred_datetime")
    if not new_dt:
        return "Please provide the new date/time." if language == "en" else "請提供新嘅日期同時間。"

    with get_db(_db(request)) as conn:
        row = conn.execute(
            """SELECT id, property_ref, proposed_datetime FROM viewings
               WHERE viewer_phone = ? AND status IN ('pending', 'confirmed')
               ORDER BY created_at DESC LIMIT 1""",
            (sender,),
        ).fetchone()
        if not row:
            return "No active viewing found to reschedule." if language == "en" else "搵唔到可以改期嘅睇樓。"
        conn.execute(
            "UPDATE viewings SET proposed_datetime = ?, status = 'pending' WHERE id = ?",
            (new_dt, row["id"]),
        )
    return render_message("reschedule", {
        "property_ref": row["property_ref"],
        "old_datetime": row["proposed_datetime"],
        "new_datetime": new_dt,
    }, language)


def _handle_availability(request: Request, parsed: dict, language: str) -> str:
    property_ref = parsed.get("property_ref")
    if not property_ref:
        return "Which property are you interested in?" if language == "en" else "你想睇邊個物業？"

    preferred_dt = parsed.get("preferred_datetime")
    target = date.today()
    if preferred_dt:
        try:
            target = datetime.fromisoformat(preferred_dt).date()
        except ValueError:
            pass

    slots = get_available_slots(_db(request), property_ref, target)
    available = [s for s in slots if s["available"]]
    if not available:
        return f"No available slots for {property_ref} on {target}." if language == "en" else f"{property_ref} 喺 {target} 冇空餘時段。"

    lines = [f"Available slots for {property_ref} on {target}:" if language == "en" else f"{property_ref} 喺 {target} 嘅可預約時段："]
    for s in available[:8]:
        lines.append(f"  • {s['start']} – {s['end']}")
    if len(available) > 8:
        lines.append(f"  ... and {len(available) - 8} more")
    return "\n".join(lines)


def _log_message(db_path: str, *, direction: str, phone: str, text: str, viewing_id: int | None) -> None:
    try:
        with get_db(db_path) as conn:
            conn.execute(
                """INSERT INTO message_log (viewing_id, direction, phone, message_text)
                   VALUES (?, ?, ?, ?)""",
                (viewing_id, direction, phone, text),
            )
    except Exception as exc:
        logger.warning("Failed to log message: %s", exc)


# ── Manual Viewing CRUD ──────────────────────────────────────────────────

class CreateViewingRequest(BaseModel):
    property_ref: str
    property_address: str | None = None
    district: str | None = None
    viewer_name: str | None = None
    viewer_phone: str
    landlord_phone: str | None = None
    agent_phone: str | None = None
    proposed_datetime: str
    notes: str | None = None


@router.post("/viewings")
async def create_viewing(request: Request, body: CreateViewingRequest) -> dict[str, Any]:
    """Create a new viewing manually."""
    with get_db(_db(request)) as conn:
        cursor = conn.execute(
            """INSERT INTO viewings
               (property_ref, property_address, district, viewer_name, viewer_phone,
                landlord_phone, agent_phone, proposed_datetime, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (body.property_ref, body.property_address, body.district,
             body.viewer_name, body.viewer_phone, body.landlord_phone,
             body.agent_phone, body.proposed_datetime, body.notes),
        )
        viewing_id = cursor.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="viewing-bot",
        summary=f"Manual viewing #{viewing_id} created: {body.property_ref}",
    )
    return {"id": viewing_id, "status": "pending"}


@router.get("/viewings/today")
async def viewings_today(request: Request) -> list[dict[str, Any]]:
    """List all viewings scheduled for today."""
    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT * FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) = ?
               ORDER BY COALESCE(confirmed_datetime, proposed_datetime)""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


@router.get("/viewings/week")
async def viewings_week(request: Request) -> list[dict[str, Any]]:
    """List viewings for the current week (Monday–Sunday) for calendar display."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT * FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) BETWEEN ? AND ?
                 AND status != 'cancelled'
               ORDER BY COALESCE(confirmed_datetime, proposed_datetime)""",
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()

    events: list[dict[str, Any]] = []
    for r in rows:
        v = dict(r)
        dt_str = v.get("confirmed_datetime") or v.get("proposed_datetime") or ""
        v["calendar_date"] = dt_str[:10] if dt_str else ""
        v["calendar_time"] = dt_str[11:16] if len(dt_str) > 11 else ""
        events.append(v)
    return events


# ── Viewing Actions ───────────────────────────────────────────────────────

class ConfirmRequest(BaseModel):
    party: str  # "viewer" or "landlord"


@router.post("/viewings/{viewing_id}/confirm")
async def confirm_viewing(request: Request, viewing_id: int, body: ConfirmRequest) -> dict[str, Any]:
    """Confirm a viewing, specifying which party is confirming."""
    field = "viewer_confirmed" if body.party == "viewer" else "landlord_confirmed"
    with get_db(_db(request)) as conn:
        conn.execute(f"UPDATE viewings SET {field} = 1 WHERE id = ?", (viewing_id,))

        row = conn.execute(
            "SELECT viewer_confirmed, landlord_confirmed FROM viewings WHERE id = ?",
            (viewing_id,),
        ).fetchone()
        if not row:
            return {"error": "Viewing not found"}

        both_confirmed = row["viewer_confirmed"] and row["landlord_confirmed"]
        if both_confirmed:
            conn.execute(
                """UPDATE viewings SET status = 'confirmed',
                   confirmed_datetime = proposed_datetime WHERE id = ?""",
                (viewing_id,),
            )

    status = "confirmed" if both_confirmed else "partially_confirmed"
    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="viewing-bot",
        summary=f"Viewing #{viewing_id} {body.party} confirmed ({status})",
    )
    return {"id": viewing_id, "party": body.party, "status": status}


class CancelRequest(BaseModel):
    reason: str = ""


@router.post("/viewings/{viewing_id}/cancel")
async def cancel_viewing(request: Request, viewing_id: int, body: CancelRequest) -> dict[str, Any]:
    """Cancel a viewing with an optional reason."""
    with get_db(_db(request)) as conn:
        row = conn.execute("SELECT status FROM viewings WHERE id = ?", (viewing_id,)).fetchone()
        if not row:
            return {"error": "Viewing not found"}
        if row["status"] == "cancelled":
            return {"error": "Already cancelled"}

        conn.execute(
            """UPDATE viewings SET status = 'cancelled',
               notes = COALESCE(notes || '\\n', '') || ? WHERE id = ?""",
            (f"Cancelled: {body.reason}" if body.reason else "Cancelled", viewing_id),
        )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="viewing-bot",
        summary=f"Viewing #{viewing_id} cancelled",
        details=body.reason,
    )
    return {"id": viewing_id, "status": "cancelled"}


class RescheduleRequest(BaseModel):
    new_datetime: str


@router.post("/viewings/{viewing_id}/reschedule")
async def reschedule_viewing(request: Request, viewing_id: int, body: RescheduleRequest) -> dict[str, Any]:
    """Propose a new time for an existing viewing."""
    with get_db(_db(request)) as conn:
        row = conn.execute(
            "SELECT property_ref, proposed_datetime FROM viewings WHERE id = ?",
            (viewing_id,),
        ).fetchone()
        if not row:
            return {"error": "Viewing not found"}

        conn.execute(
            """UPDATE viewings SET proposed_datetime = ?, confirmed_datetime = NULL,
               status = 'pending', viewer_confirmed = 0, landlord_confirmed = 0
               WHERE id = ?""",
            (body.new_datetime, viewing_id),
        )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="viewing-bot",
        summary=f"Viewing #{viewing_id} rescheduled to {body.new_datetime}",
    )
    return {
        "id": viewing_id,
        "old_datetime": row["proposed_datetime"],
        "new_datetime": body.new_datetime,
        "status": "pending",
    }


# ── Route Optimisation ────────────────────────────────────────────────────

@router.get("/route/today")
async def route_today(request: Request) -> dict[str, Any]:
    """Get an optimised route for today's viewings."""
    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT * FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) = ?
                 AND status IN ('confirmed', 'pending')
               ORDER BY COALESCE(confirmed_datetime, proposed_datetime)""",
            (today,),
        ).fetchall()

    viewings = [dict(r) for r in rows]
    if not viewings:
        return {"route": [], "total_distance_km": 0, "count": 0}

    optimised = optimize_route(viewings)
    for v in optimised:
        lat, lon = HK_DISTRICT_COORDS.get(v.get("district", ""), (22.3193, 114.1694))
        v["lat"] = lat
        v["lon"] = lon
    total_km = optimised[-1]["cumulative_distance_km"] if optimised else 0
    return {"route": optimised, "total_distance_km": total_km, "count": len(optimised)}


# ── Weather ───────────────────────────────────────────────────────────────

@router.get("/weather")
async def weather(request: Request) -> dict[str, Any]:
    """Get current HK Observatory weather warnings and safety assessment."""
    warnings = await get_weather_warnings()
    unsafe = is_viewing_unsafe(warnings)

    result: dict[str, Any] = {
        "warnings": warnings,
        "is_unsafe": unsafe,
        "recommendation": "All clear for viewings" if not unsafe else "Viewings should be postponed",
    }

    if unsafe:
        cancelled = await auto_cancel_unsafe_viewings(
            _db(request), warnings, mona_db_path=_mona_db(request),
        )
        result["auto_cancelled_ids"] = cancelled

    return result


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/partials/weather-banner", response_class=HTMLResponse)
async def weather_banner_partial(request: Request) -> HTMLResponse:
    """Return weather alert banner HTML (empty if no warnings)."""
    warnings = await get_weather_warnings()
    unsafe = is_viewing_unsafe(warnings)
    return templates.TemplateResponse(
        "viewing_bot/partials/weather_banner.html",
        _ctx(request, warnings=warnings, is_unsafe=unsafe, recommendation="Viewings should be postponed" if unsafe else "All clear for viewings"),
    )


@router.get("/partials/today-coordination", response_class=HTMLResponse)
async def today_coordination_partial(request: Request) -> HTMLResponse:
    """Return coordination cards for today's viewings."""
    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        viewings = [dict(r) for r in conn.execute(
            """SELECT * FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) = ?
                 AND status != 'cancelled'
               ORDER BY COALESCE(confirmed_datetime, proposed_datetime)""",
            (today,),
        ).fetchall()]
    return templates.TemplateResponse(
        "viewing_bot/partials/today_coordination.html",
        _ctx(request, viewings=viewings),
    )


@router.get("/partials/follow-ups", response_class=HTMLResponse)
async def follow_ups_partial(request: Request, interest: str | None = None) -> HTMLResponse:
    """Return follow-ups table, optionally filtered by interest level."""
    with get_db(_db(request)) as conn:
        query = """
            SELECT f.*, v.property_ref, v.viewer_name,
                   DATE(COALESCE(v.confirmed_datetime, v.proposed_datetime)) as viewing_date
            FROM follow_ups f
            JOIN viewings v ON v.id = f.viewing_id
        """
        params: list[Any] = []
        if interest:
            query += " WHERE f.interest_level = ?"
            params.append(interest)
        query += " ORDER BY f.sent_at DESC"
        rows = conn.execute(query, params).fetchall()
    follow_ups = [dict(r) for r in rows]
    return templates.TemplateResponse(
        "viewing_bot/partials/follow_ups.html",
        _ctx(request, follow_ups=follow_ups),
    )


@router.get("/partials/route-details", response_class=HTMLResponse)
async def route_details_partial(request: Request) -> HTMLResponse:
    """Return route summary for today's optimised viewings."""
    data = await route_today(request)
    return templates.TemplateResponse(
        "viewing_bot/partials/route_details.html",
        _ctx(
            request,
            route=data.get("route", []),
            total_distance_km=data.get("total_distance_km", 0),
            count=data.get("count", 0),
        ),
    )


@router.get("/partials/calendar", response_class=HTMLResponse)
async def calendar_partial(request: Request) -> Any:
    """Return calendar events JSON for htmx consumption."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT id, property_ref, property_address, district,
                      COALESCE(confirmed_datetime, proposed_datetime) as dt,
                      status, viewer_name
               FROM viewings
               WHERE DATE(COALESCE(confirmed_datetime, proposed_datetime)) BETWEEN ? AND ?
               ORDER BY dt""",
            (monday.isoformat(), sunday.isoformat()),
        ).fetchall()

    events = []
    for r in rows:
        v = dict(r)
        events.append({
            "id": v["id"],
            "title": f"{v.get('property_ref', '')} — {v.get('viewer_name', '')}",
            "start": v["dt"],
            "status": v["status"],
            "district": v.get("district", ""),
            "address": v.get("property_address", ""),
        })

    import json
    return HTMLResponse(json.dumps(events), media_type="application/json")


@router.get("/partials/coordination/{viewing_id}", response_class=HTMLResponse)
async def coordination_partial(request: Request, viewing_id: int) -> HTMLResponse:
    """Return an htmx partial for the coordination board of a single viewing."""
    with get_db(_db(request)) as conn:
        viewing = conn.execute("SELECT * FROM viewings WHERE id = ?", (viewing_id,)).fetchone()
        if not viewing:
            return HTMLResponse("<div class='text-red-500'>Viewing not found</div>")
        viewing = dict(viewing)

        messages = [dict(r) for r in conn.execute(
            "SELECT * FROM message_log WHERE viewing_id = ? ORDER BY timestamp",
            (viewing_id,),
        ).fetchall()]

        follow_ups = [dict(r) for r in conn.execute(
            "SELECT * FROM follow_ups WHERE viewing_id = ? ORDER BY sent_at DESC",
            (viewing_id,),
        ).fetchall()]

    return templates.TemplateResponse(
        "viewing_bot/partials/coordination.html",
        _ctx(request, viewing=viewing, messages=messages, follow_ups=follow_ups),
    )
