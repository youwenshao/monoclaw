"""TableMaster AI — FastAPI routes for the F&B reservation system."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from fnb_hospitality.table_master.booking.assigner import assign_table
from fnb_hospitality.table_master.booking.confirmer import (
    auto_confirm_booking,
    confirm_booking_manual,
)
from fnb_hospitality.table_master.booking.engine import (
    check_capacity,
    compute_end_time,
    detect_conflicts,
    suggest_nearest_slot,
)
from fnb_hospitality.table_master.booking.parser import parse_booking_text
from fnb_hospitality.table_master.channels.manual import (
    ManualBookingRequest,
    create_manual_booking,
)
from fnb_hospitality.table_master.channels.whatsapp import handle_incoming as wa_handle
from fnb_hospitality.table_master.inventory.capacity import (
    calculate_remaining_capacity,
    get_daily_capacity_overview,
)
from fnb_hospitality.table_master.inventory.tables import (
    get_all_tables,
    get_table,
    get_table_summary,
    get_tables_by_status,
    update_table_status,
)

router = APIRouter(prefix="/table-master", tags=["TableMaster"])

templates = Jinja2Templates(directory="fnb_hospitality/dashboard/templates")

logger = logging.getLogger("openclaw.table_master.routes")

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


# ── Helpers ───────────────────────────────────────────────────────────────

def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "table-master",
        **extra,
    }


def _db(request: Request) -> str:
    return request.app.state.db_paths["table_master"]


def _mona_db(request: Request) -> str:
    return request.app.state.db_paths["mona_events"]


# ── Main Page ─────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def table_master_page(request: Request) -> HTMLResponse:
    """Render the main TableMaster dashboard."""
    db_path = _db(request)
    today = date.today().isoformat()

    tables = get_all_tables(db_path)
    summary = get_table_summary(db_path)

    with get_db(db_path) as conn:
        today_bookings = [dict(r) for r in conn.execute(
            """SELECT b.*, t.table_number
               FROM bookings b
               LEFT JOIN tables t ON t.id = b.table_id
               WHERE b.booking_date = ?
               ORDER BY b.booking_time""",
            (today,),
        ).fetchall()]

        pending_count = conn.execute(
            "SELECT COUNT(*) FROM bookings WHERE status = 'pending' AND booking_date >= ?",
            (today,),
        ).fetchone()[0]

        total_covers_today = conn.execute(
            "SELECT COALESCE(SUM(party_size), 0) FROM bookings WHERE booking_date = ? AND status IN ('pending', 'confirmed')",
            (today,),
        ).fetchone()[0]

    capacity = calculate_remaining_capacity(db_path, today, "19:00")

    stats = {
        "total_tables": len(tables),
        "available": summary.get("available", 0),
        "reserved": summary.get("reserved", 0),
        "occupied": summary.get("occupied", 0),
        "today_bookings": len(today_bookings),
        "pending_bookings": pending_count,
        "total_covers_today": total_covers_today,
        "utilisation": capacity.get("utilisation_percent", 0),
    }

    return templates.TemplateResponse(
        "table_master/index.html",
        _ctx(
            request,
            tables=tables,
            bookings=today_bookings,
            stats=stats,
            today=today,
        ),
    )


# ── Booking CRUD ──────────────────────────────────────────────────────────

@router.post("/bookings")
async def create_booking(request: Request, body: ManualBookingRequest) -> dict[str, Any]:
    """Create a booking from the dashboard (phone / walk-in)."""
    result = create_manual_booking(body, db_path=_db(request), mona_db_path=_mona_db(request))

    assignment = assign_table(
        _db(request),
        result.id,
        party_size=body.party_size,
        booking_date=body.booking_date,
        booking_time=body.booking_time,
        special_requests=body.special_requests,
    )

    if assignment.get("assigned"):
        end_time = compute_end_time(body.booking_time, body.booking_date)
        with get_db(_db(request)) as conn:
            conn.execute(
                "UPDATE bookings SET end_time = ? WHERE id = ?",
                (end_time, result.id),
            )

        await auto_confirm_booking(
            _db(request), result.id, mona_db_path=_mona_db(request), send_whatsapp=False,
        )

    return {
        "booking": result.model_dump(),
        "assignment": assignment,
    }


@router.get("/bookings/today")
async def bookings_today(request: Request) -> list[dict[str, Any]]:
    """List all bookings for today."""
    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT b.*, t.table_number
               FROM bookings b
               LEFT JOIN tables t ON t.id = b.table_id
               WHERE b.booking_date = ?
               ORDER BY b.booking_time""",
            (today,),
        ).fetchall()
    return [dict(r) for r in rows]


class ConfirmBookingRequest(BaseModel):
    send_notification: bool = True


@router.post("/bookings/{booking_id}/confirm")
async def confirm_booking(
    request: Request,
    booking_id: int,
    body: ConfirmBookingRequest | None = None,
) -> dict[str, Any]:
    """Confirm a pending booking."""
    send = body.send_notification if body else True
    config = request.app.state.config

    twilio_client = None
    twilio_from = ""
    if send and config.messaging.twilio_account_sid:
        try:
            from twilio.rest import Client
            twilio_client = Client(config.messaging.twilio_account_sid, config.messaging.twilio_auth_token)
            twilio_from = config.messaging.twilio_whatsapp_from
        except Exception:
            pass

    result = await confirm_booking_manual(
        _db(request),
        booking_id,
        mona_db_path=_mona_db(request),
        twilio_client=twilio_client,
        twilio_from=twilio_from,
    )
    return result


class CancelBookingRequest(BaseModel):
    reason: str = ""


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(
    request: Request,
    booking_id: int,
    body: CancelBookingRequest | None = None,
) -> dict[str, Any]:
    """Cancel a booking."""
    reason = body.reason if body else ""

    with get_db(_db(request)) as conn:
        row = conn.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,)).fetchone()
        if not row:
            return {"error": "Booking not found"}

        booking = dict(row)
        if booking["status"] == "cancelled":
            return {"error": "Already cancelled"}

        conn.execute(
            "UPDATE bookings SET status = 'cancelled' WHERE id = ?",
            (booking_id,),
        )

        if booking.get("table_id"):
            conn.execute(
                "UPDATE tables SET status = 'available', current_booking_id = NULL WHERE id = ?",
                (booking["table_id"],),
            )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="table-master",
        summary=f"Booking #{booking_id} cancelled ({booking['guest_name']})",
        details=reason,
    )
    return {"id": booking_id, "status": "cancelled", "reason": reason}


# ── WhatsApp Webhook ──────────────────────────────────────────────────────

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> PlainTextResponse:
    """Handle incoming Twilio WhatsApp messages."""
    form = await request.form()
    data = dict(form)

    reply = await wa_handle(
        data,
        llm=request.app.state.llm,
        db_path=_db(request),
        mona_db_path=_mona_db(request),
        parse_fn=parse_booking_text,
        config=request.app.state.config,
    )
    return PlainTextResponse(reply)


# ── Table Management ──────────────────────────────────────────────────────

class UpdateTableStatusRequest(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"available", "reserved", "occupied", "clearing", "maintenance"}
        if v.lower() not in allowed:
            raise ValueError(f"Status must be one of: {', '.join(sorted(allowed))}")
        return v.lower()


@router.post("/tables/{table_id}/status")
async def update_status(
    request: Request,
    table_id: int,
    body: UpdateTableStatusRequest,
) -> dict[str, Any]:
    """Transition a table to a new status."""
    result = update_table_status(_db(request), table_id, body.status)

    if "error" not in result:
        emit_event(
            _mona_db(request),
            event_type="info",
            tool_name="table-master",
            summary=f"Table {result['table_number']}: {result['old_status']} → {result['new_status']}",
        )

    return result


@router.get("/tables")
async def list_tables(request: Request, status: str | None = None) -> list[dict[str, Any]]:
    """List tables, optionally filtered by status."""
    if status:
        return get_tables_by_status(_db(request), status)
    return get_all_tables(_db(request))


@router.get("/tables/{table_id}")
async def get_table_detail(request: Request, table_id: int) -> dict[str, Any]:
    """Get details for a single table."""
    table = get_table(_db(request), table_id)
    if not table:
        return {"error": "Table not found"}
    return table


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/partials/floor-plan", response_class=HTMLResponse)
async def floor_plan_partial(request: Request) -> HTMLResponse:
    """Return the floor plan grid as an htmx partial."""
    tables = get_all_tables(_db(request))
    summary = get_table_summary(_db(request))
    return templates.TemplateResponse(
        "table_master/partials/floor_plan.html",
        _ctx(request, tables=tables, summary=summary),
    )


@router.get("/partials/booking-list", response_class=HTMLResponse)
async def booking_list_partial(
    request: Request,
    target_date: str | None = None,
    status: str | None = None,
) -> HTMLResponse:
    """Return the booking list as an htmx partial."""
    target = target_date or date.today().isoformat()

    with get_db(_db(request)) as conn:
        query = """
            SELECT b.*, t.table_number
            FROM bookings b
            LEFT JOIN tables t ON t.id = b.table_id
            WHERE b.booking_date = ?
        """
        params: list[Any] = [target]
        if status:
            query += " AND b.status = ?"
            params.append(status)
        query += " ORDER BY b.booking_time"

        bookings = [dict(r) for r in conn.execute(query, params).fetchall()]

    return templates.TemplateResponse(
        "table_master/partials/booking_list.html",
        _ctx(request, bookings=bookings, target_date=target),
    )


@router.get("/partials/table-detail/{table_id}", response_class=HTMLResponse)
async def table_detail_partial(request: Request, table_id: int) -> HTMLResponse:
    """Return table detail card as an htmx partial."""
    table = get_table(_db(request), table_id)
    if not table:
        return HTMLResponse('<div class="text-red-500">Table not found</div>')

    today = date.today().isoformat()
    with get_db(_db(request)) as conn:
        upcoming = [dict(r) for r in conn.execute(
            """SELECT * FROM bookings
               WHERE table_id = ? AND booking_date >= ? AND status IN ('pending', 'confirmed')
               ORDER BY booking_date, booking_time
               LIMIT 5""",
            (table_id, today),
        ).fetchall()]

    return templates.TemplateResponse(
        "table_master/partials/table_detail.html",
        _ctx(request, table=table, upcoming_bookings=upcoming),
    )


# ── Analytics ─────────────────────────────────────────────────────────────

@router.get("/analytics/heatmap")
async def booking_heatmap(
    request: Request,
    days: int = 14,
) -> dict[str, Any]:
    """Return booking counts grouped by date and hour for heatmap rendering.

    Response shape::

        {
            "start_date": "2026-02-20",
            "end_date": "2026-03-06",
            "data": [
                {"date": "2026-03-06", "hour": 19, "count": 5, "covers": 18},
                ...
            ]
        }
    """
    end = date.today()
    start = end - timedelta(days=days - 1)

    with get_db(_db(request)) as conn:
        rows = conn.execute(
            """SELECT
                   booking_date,
                   CAST(SUBSTR(booking_time, 1, 2) AS INTEGER) AS hour,
                   COUNT(*) AS count,
                   SUM(party_size) AS covers
               FROM bookings
               WHERE booking_date BETWEEN ? AND ?
                 AND status IN ('pending', 'confirmed', 'completed')
               GROUP BY booking_date, hour
               ORDER BY booking_date, hour""",
            (start.isoformat(), end.isoformat()),
        ).fetchall()

    data = [dict(r) for r in rows]
    return {
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "data": data,
    }


@router.get("/analytics/capacity")
async def capacity_overview(
    request: Request,
    target_date: str | None = None,
) -> dict[str, Any]:
    """Return capacity overview for a given date."""
    target = target_date or date.today().isoformat()
    return get_daily_capacity_overview(_db(request), target)


# ── Channel Inbox ─────────────────────────────────────────────────────────

@router.get("/inbox")
async def channel_inbox(
    request: Request,
    channel: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """List recent bookings grouped by inbound channel."""
    with get_db(_db(request)) as conn:
        query = """
            SELECT b.*, t.table_number
            FROM bookings b
            LEFT JOIN tables t ON t.id = b.table_id
        """
        params: list[Any] = []
        if channel:
            query += " WHERE b.channel = ?"
            params.append(channel)
        query += " ORDER BY b.created_at DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()

    return [dict(r) for r in rows]
