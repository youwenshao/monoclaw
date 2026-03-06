"""QueueBot FastAPI routes — staff dashboard, customer-facing queue, SSE, POS import."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from openclaw_shared.auth import PINAuthMiddleware
from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from fnb_hospitality.queue_bot.analytics.reports import (
    average_wait_times,
    daily_summary,
    party_size_distribution,
    peak_queue_lengths,
    walkout_rates,
)
from fnb_hospitality.queue_bot.pos.integration import import_csv
from fnb_hospitality.queue_bot.queue.estimator import estimate_wait
from fnb_hospitality.queue_bot.queue.manager import (
    call_next,
    get_active_queue,
    get_queue_position,
    join_queue,
    mark_left,
    remove_guest,
    seat_guest,
    skip_guest,
    typhoon_clear,
)
from fnb_hospitality.queue_bot.queue.notifier import send_table_ready
from fnb_hospitality.queue_bot.web.qr_generator import generate_qr

router = APIRouter(prefix="/queue-bot", tags=["QueueBot"])

templates = Jinja2Templates(directory="fnb_hospitality/dashboard/templates")

# Customer-facing paths that skip PIN authentication
PINAuthMiddleware.SKIP_PREFIXES = PINAuthMiddleware.SKIP_PREFIXES + (
    "/queue-bot/join",
    "/queue-bot/status",
    "/queue-bot/display",
    "/queue-bot/sse",
)

HK_PHONE_RE = re.compile(r"^\+852[5679]\d{7}$")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "queue-bot",
        **extra,
    }


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["queue_bot"])


def _mona_db(request: Request) -> str:
    return str(request.app.state.db_paths["mona_events"])


# ── Staff dashboard ────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def queue_dashboard(request: Request) -> HTMLResponse:
    db = _db(request)
    queue = get_active_queue(db)
    today = date.today().isoformat()

    with get_db(db) as conn:
        today_total = conn.execute(
            "SELECT COUNT(*) FROM queue_entries WHERE DATE(joined_at) = ?",
            (today,),
        ).fetchone()[0]
        today_seated = conn.execute(
            "SELECT COUNT(*) FROM queue_entries "
            "WHERE DATE(joined_at) = ? AND status = 'seated'",
            (today,),
        ).fetchone()[0]
        today_left = conn.execute(
            "SELECT COUNT(*) FROM queue_entries "
            "WHERE DATE(joined_at) = ? AND status = 'left'",
            (today,),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "queue_bot/index.html",
        _ctx(
            request,
            queue=queue,
            today_total=today_total,
            today_seated=today_seated,
            today_left=today_left,
        ),
    )


# ── Customer-facing join page (NO AUTH) ────────────────────────────────────


@router.get("/join", response_class=HTMLResponse)
async def join_page(request: Request) -> HTMLResponse:
    config = request.app.state.config
    restaurant_name = config.extra.get("restaurant_name", "")
    return templates.TemplateResponse(
        "queue_bot/join.html",
        {
            "request": request,
            "config": config,
            "restaurant_name": restaurant_name,
            "error": request.query_params.get("error"),
        },
    )


class JoinQueueForm(BaseModel):
    guest_name: str
    guest_phone: str
    party_size: int
    seating_preference: str | None = None
    language_pref: str = "zh"


@router.post("/join")
async def process_join(request: Request) -> RedirectResponse:
    form = await request.form()
    guest_name = str(form.get("guest_name", "")).strip()
    guest_phone = str(form.get("guest_phone", "")).strip()
    party_size_raw = str(form.get("party_size", "1")).strip()
    seating_preference = str(form.get("seating_preference", "")).strip() or None
    language_pref = str(form.get("language_pref", "zh")).strip()

    if not guest_phone.startswith("+852"):
        guest_phone = "+852" + guest_phone.lstrip("+")

    try:
        party_size = max(1, int(party_size_raw))
    except ValueError:
        party_size = 1

    db = _db(request)
    est = estimate_wait(db, party_size)

    try:
        entry = join_queue(
            db,
            guest_name=guest_name,
            guest_phone=guest_phone,
            party_size=party_size,
            seating_preference=seating_preference,
            language_pref=language_pref,
            channel="qr",
            estimated_wait=est,
        )
    except ValueError:
        return RedirectResponse("/queue-bot/join?error=invalid_phone", status_code=303)

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="queue-bot",
        summary=f"Queue #{entry['queue_number']}: {guest_name} ({party_size} pax) joined",
    )

    return RedirectResponse(f"/queue-bot/status/{entry['id']}", status_code=303)


# ── Customer status page (NO AUTH) ────────────────────────────────────────


@router.get("/status/{queue_id}", response_class=HTMLResponse)
async def status_page(request: Request, queue_id: int) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        row = conn.execute(
            "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Queue entry not found")

    entry = dict(row)
    position = get_queue_position(db, queue_id)
    est = estimate_wait(db, entry["party_size"]) if position else 0
    restaurant_name = request.app.state.config.extra.get("restaurant_name", "")

    return templates.TemplateResponse(
        "queue_bot/status.html",
        {
            "request": request,
            "config": request.app.state.config,
            "entry": entry,
            "position": position,
            "estimated_wait": est,
            "restaurant_name": restaurant_name,
        },
    )


# ── SSE live updates (NO AUTH) ────────────────────────────────────────────


@router.get("/sse/{queue_id}")
async def sse_updates(request: Request, queue_id: int) -> EventSourceResponse:
    db = _db(request)

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break

            with get_db(db) as conn:
                row = conn.execute(
                    "SELECT * FROM queue_entries WHERE id = ?", (queue_id,),
                ).fetchone()

            if not row:
                yield {"event": "error", "data": json.dumps({"error": "not_found"})}
                break

            entry = dict(row)
            position = get_queue_position(db, queue_id)
            est = estimate_wait(db, entry["party_size"]) if position else 0

            payload = {
                "id": entry["id"],
                "queue_number": entry["queue_number"],
                "status": entry["status"],
                "position": position,
                "estimated_wait": est,
            }
            yield {"event": "update", "data": json.dumps(payload)}

            if entry["status"] in ("seated", "left", "removed"):
                break

            await asyncio.sleep(10)

    return EventSourceResponse(event_generator())


# ── TV queue display (NO AUTH) ─────────────────────────────────────────────


@router.get("/display", response_class=HTMLResponse)
async def tv_display(request: Request) -> HTMLResponse:
    db = _db(request)
    queue = get_active_queue(db)
    restaurant_name = request.app.state.config.extra.get("restaurant_name", "")

    return templates.TemplateResponse(
        "queue_bot/display.html",
        {
            "request": request,
            "config": request.app.state.config,
            "queue": queue,
            "restaurant_name": restaurant_name,
        },
    )


# ── Staff actions ──────────────────────────────────────────────────────────


@router.post("/call-next")
async def api_call_next(request: Request) -> dict[str, Any]:
    db = _db(request)
    entry = call_next(db)
    if not entry:
        raise HTTPException(status_code=404, detail="No guests waiting")

    config = request.app.state.config
    messaging = getattr(request.app.state, "messaging", None)
    restaurant_name = config.extra.get("restaurant_name", "")

    await send_table_ready(
        messaging,
        entry["guest_phone"],
        entry["queue_number"],
        language="zh",
        restaurant_name=restaurant_name,
        db_path=db,
        queue_entry_id=entry["id"],
    )

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="queue-bot",
        summary=f"Called queue #{entry['queue_number']}: {entry.get('guest_name', 'Guest')}",
    )

    return entry


@router.post("/seat/{queue_id}")
async def api_seat(request: Request, queue_id: int) -> dict[str, Any]:
    db = _db(request)
    try:
        entry = seat_guest(db, queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="queue-bot",
        summary=(
            f"Seated queue #{entry['queue_number']} "
            f"({entry['party_size']} pax, waited {entry.get('actual_wait_minutes', '?')} min)"
        ),
    )
    return entry


@router.post("/skip/{queue_id}")
async def api_skip(request: Request, queue_id: int) -> dict[str, Any]:
    db = _db(request)
    try:
        entry = skip_guest(db, queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    emit_event(
        _mona_db(request),
        event_type="info",
        tool_name="queue-bot",
        summary=f"Skipped queue #{entry['queue_number']} — moved to back",
    )
    return entry


@router.post("/remove/{queue_id}")
async def api_remove(request: Request, queue_id: int) -> dict[str, Any]:
    db = _db(request)
    try:
        entry = remove_guest(db, queue_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    emit_event(
        _mona_db(request),
        event_type="info",
        tool_name="queue-bot",
        summary=f"Removed queue #{entry['queue_number']} from queue",
    )
    return entry


# ── Typhoon T8+ auto-clear ────────────────────────────────────────────────


@router.post("/typhoon-clear")
async def api_typhoon_clear(request: Request) -> dict[str, Any]:
    db = _db(request)
    cleared = typhoon_clear(db)

    emit_event(
        _mona_db(request),
        event_type="alert",
        tool_name="queue-bot",
        summary=f"Typhoon T8+ signal: {cleared} queue entries cleared",
        requires_human_action=True,
    )
    return {"cleared": cleared}


# ── QR code ────────────────────────────────────────────────────────────────


@router.get("/qr")
async def get_qr(request: Request) -> FileResponse:
    config = request.app.state.config
    base_url = f"http://localhost:{config.port}"
    workspace = request.app.state.workspace
    qr_path = workspace / "queue_qr.png"

    generate_qr(base_url, qr_path)

    return FileResponse(
        str(qr_path),
        media_type="image/png",
        filename="queue_qr.png",
    )


# ── POS import ─────────────────────────────────────────────────────────────


@router.post("/pos/import")
async def pos_import(
    request: Request,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = (await file.read()).decode("utf-8-sig")
    db = _db(request)

    try:
        result = import_csv(db, content)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result["imported"] > 0:
        emit_event(
            _mona_db(request),
            event_type="action_completed",
            tool_name="queue-bot",
            summary=f"POS import: {result['imported']} turnover records added",
        )
    return result


# ── HTMX Partials ─────────────────────────────────────────────────────────


@router.get("/partials/queue-list", response_class=HTMLResponse)
async def partial_queue_list(request: Request) -> HTMLResponse:
    db = _db(request)
    queue = get_active_queue(db)
    return templates.TemplateResponse(
        "queue_bot/partials/queue_list.html",
        {"request": request, "queue": queue},
    )


@router.get("/partials/analytics", response_class=HTMLResponse)
async def partial_analytics(request: Request) -> HTMLResponse:
    db = _db(request)
    wait_times = average_wait_times(db)
    walkouts = walkout_rates(db)
    peaks = peak_queue_lengths(db)
    distribution = party_size_distribution(db)
    summary = daily_summary(db)

    return templates.TemplateResponse(
        "queue_bot/partials/analytics.html",
        {
            "request": request,
            "wait_times": wait_times,
            "walkouts": walkouts,
            "peaks": peaks,
            "distribution": distribution,
            "summary": summary,
        },
    )
