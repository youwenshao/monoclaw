"""IntakeBot FastAPI routes."""

from __future__ import annotations

import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from legal.intake_bot.conflict_checker import run_conflict_check, save_conflict_results
from legal.intake_bot.intake_form import generate_intake_form
from legal.intake_bot.engagement_letter import generate_engagement_letter
from legal.intake_bot.bot.whatsapp import handle_whatsapp_message
from legal.intake_bot.bot.telegram import handle_telegram_update

router = APIRouter(prefix="/intake-bot", tags=["IntakeBot"])
templates = Jinja2Templates(directory="legal/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "intake-bot", **extra}


def _db(request: Request) -> str:
    return str(request.app.state.db_paths["intake_bot"])


# ── Pydantic models ────────────────────────────────────────────────────────


class ClientCreate(BaseModel):
    name_en: str
    name_tc: str = ""
    hkid_last4: str = ""
    phone: str = ""
    email: str = ""
    source_channel: str = Field(default="walk_in", pattern=r"^(whatsapp|wechat|telegram|walk_in|referral|website)$")


class ScheduleMeeting(BaseModel):
    solicitor: str
    datetime: str
    duration_minutes: int = Field(default=60, ge=15, le=240)


# ── Main page ──────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
async def intake_bot_page(request: Request) -> HTMLResponse:
    db = _db(request)
    today = date.today().isoformat()

    with get_db(db) as conn:
        clients = [dict(r) for r in conn.execute(
            "SELECT * FROM clients ORDER BY intake_date DESC LIMIT 50"
        ).fetchall()]

        pending_count = conn.execute(
            "SELECT COUNT(*) FROM clients WHERE status = 'pending_review'"
        ).fetchone()[0]

        matters = [dict(r) for r in conn.execute(
            """SELECT m.*, c.name_en as client_name
               FROM matters m
               JOIN clients c ON c.id = m.client_id
               ORDER BY m.created_date DESC LIMIT 50"""
        ).fetchall()]

        upcoming_appointments = [dict(r) for r in conn.execute(
            """SELECT a.*, c.name_en as client_name
               FROM appointments a
               JOIN clients c ON c.id = a.client_id
               WHERE a.status IN ('scheduled', 'confirmed')
               ORDER BY a.datetime ASC LIMIT 20"""
        ).fetchall()]

        recent_conflicts = [dict(r) for r in conn.execute(
            """SELECT cc.*, m.adverse_party_name, c.name_en as client_name
               FROM conflict_checks cc
               JOIN matters m ON m.id = cc.matter_id
               JOIN clients c ON c.id = m.client_id
               WHERE cc.result != 'clear'
               ORDER BY cc.check_date DESC LIMIT 10"""
        ).fetchall()]

        stats = {
            "total_clients": conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0],
            "pending_review": pending_count,
            "active_matters": conn.execute(
                "SELECT COUNT(*) FROM matters WHERE status IN ('intake', 'active')"
            ).fetchone()[0],
            "today_appointments": conn.execute(
                "SELECT COUNT(*) FROM appointments WHERE DATE(datetime) = ?",
                (today,),
            ).fetchone()[0],
        }

    return templates.TemplateResponse(
        "intake_bot/index.html",
        _ctx(
            request,
            clients=clients,
            matters=matters,
            appointments=upcoming_appointments,
            conflicts=recent_conflicts,
            stats=stats,
            today=today,
        ),
    )


# ── Client CRUD ────────────────────────────────────────────────────────────


@router.post("/clients")
async def create_client(request: Request, body: ClientCreate) -> dict[str, Any]:
    db = _db(request)

    from legal.intake_bot.fuzzy_match import validate_hkid_last4
    if body.hkid_last4 and not validate_hkid_last4(body.hkid_last4):
        raise HTTPException(status_code=422, detail="Invalid HKID last-4 format (expected e.g. A123)")

    with get_db(db) as conn:
        conn.execute(
            """INSERT INTO clients
               (name_en, name_tc, hkid_last4, phone, email, source_channel, status)
               VALUES (?, ?, ?, ?, ?, ?, 'pending_review')""",
            (body.name_en, body.name_tc, body.hkid_last4,
             body.phone, body.email, body.source_channel),
        )
        client_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="info",
        tool_name="intake-bot",
        summary=f"New client registered: {body.name_en} via {body.source_channel}",
    )

    return {"id": client_id, "name_en": body.name_en, "status": "pending_review"}


@router.get("/clients/{client_id}")
async def client_detail(request: Request, client_id: int) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()

        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        client = dict(client_row)

        client_matters = [dict(r) for r in conn.execute(
            "SELECT * FROM matters WHERE client_id = ? ORDER BY created_date DESC",
            (client_id,),
        ).fetchall()]

        client_appointments = [dict(r) for r in conn.execute(
            "SELECT * FROM appointments WHERE client_id = ? ORDER BY datetime DESC",
            (client_id,),
        ).fetchall()]

        client_conversations = [dict(r) for r in conn.execute(
            "SELECT * FROM conversations WHERE client_id = ? ORDER BY created_at DESC LIMIT 100",
            (client_id,),
        ).fetchall()]

    return {
        "client": client,
        "matters": client_matters,
        "appointments": client_appointments,
        "conversations": client_conversations,
    }


# ── Conflict checks ───────────────────────────────────────────────────────


@router.post("/conflict-check/{matter_id}")
async def run_conflict_check_route(request: Request, matter_id: int) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        matter_row = conn.execute(
            "SELECT id FROM matters WHERE id = ?", (matter_id,)
        ).fetchone()
        if not matter_row:
            raise HTTPException(status_code=404, detail="Matter not found")

    conflicts = run_conflict_check(matter_id, db)
    saved = save_conflict_results(matter_id, conflicts, db)

    if conflicts:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="alert",
            tool_name="intake-bot",
            summary=f"Conflict check for matter #{matter_id}: {len(conflicts)} potential conflict(s) found",
            details=str([c["matched_client_name"] for c in conflicts[:5]]),
        )
    else:
        emit_event(
            request.app.state.db_paths["mona_events"],
            event_type="action_completed",
            tool_name="intake-bot",
            summary=f"Conflict check for matter #{matter_id}: clear",
        )

    return {
        "matter_id": matter_id,
        "conflicts": conflicts,
        "total_checked": saved,
        "status": "potential_conflict" if conflicts else "clear",
    }


@router.get("/conflict-results/{matter_id}", response_class=HTMLResponse)
async def conflict_results_partial(request: Request, matter_id: int) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        results = [dict(r) for r in conn.execute(
            """SELECT * FROM conflict_checks
               WHERE matter_id = ?
               ORDER BY match_score DESC""",
            (matter_id,),
        ).fetchall()]

        matter_row = conn.execute(
            """SELECT m.*, c.name_en as client_name
               FROM matters m
               JOIN clients c ON c.id = m.client_id
               WHERE m.id = ?""",
            (matter_id,),
        ).fetchone()

    matter = dict(matter_row) if matter_row else {}

    return templates.TemplateResponse(
        "intake_bot/partials/conflict_results.html",
        {"request": request, "results": results, "matter": matter, "matter_id": matter_id},
    )


# ── Scheduling ─────────────────────────────────────────────────────────────


@router.post("/schedule/{client_id}")
async def schedule_meeting(
    request: Request,
    client_id: int,
    body: ScheduleMeeting,
) -> dict[str, Any]:
    db = _db(request)

    with get_db(db) as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        client = dict(client_row)

        matter_row = conn.execute(
            "SELECT id FROM matters WHERE client_id = ? ORDER BY created_date DESC LIMIT 1",
            (client_id,),
        ).fetchone()
        matter_id = matter_row[0] if matter_row else None

        conn.execute(
            """INSERT INTO appointments
               (client_id, matter_id, solicitor, datetime, duration_minutes, status)
               VALUES (?, ?, ?, ?, ?, 'scheduled')""",
            (client_id, matter_id, body.solicitor, body.datetime, body.duration_minutes),
        )
        appt_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="intake-bot",
        summary=f"Consultation scheduled: {client['name_en']} with {body.solicitor} on {body.datetime}",
    )

    return {
        "id": appt_id,
        "client_id": client_id,
        "solicitor": body.solicitor,
        "datetime": body.datetime,
        "duration_minutes": body.duration_minutes,
        "status": "scheduled",
    }


# ── Conversation viewer ───────────────────────────────────────────────────


@router.get("/conversation/{client_id}", response_class=HTMLResponse)
async def conversation_thread(request: Request, client_id: int) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        messages = [dict(r) for r in conn.execute(
            "SELECT * FROM conversations WHERE client_id = ? ORDER BY created_at ASC",
            (client_id,),
        ).fetchall()]

    return templates.TemplateResponse(
        "intake_bot/partials/conversation_thread.html",
        {"request": request, "client": dict(client_row), "messages": messages},
    )


# ── Document generation ───────────────────────────────────────────────────


@router.post("/generate-intake-form/{client_id}")
async def generate_intake_form_route(request: Request, client_id: int) -> FileResponse:
    db = _db(request)

    with get_db(db) as conn:
        client_row = conn.execute(
            "SELECT * FROM clients WHERE id = ?", (client_id,)
        ).fetchone()
        if not client_row:
            raise HTTPException(status_code=404, detail="Client not found")

        matter_row = conn.execute(
            "SELECT * FROM matters WHERE client_id = ? ORDER BY created_date DESC LIMIT 1",
            (client_id,),
        ).fetchone()

    client_data = dict(client_row)
    matter_data = dict(matter_row) if matter_row else {}

    workspace = request.app.state.workspace
    output_dir = workspace / "generated" / "intake_forms"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = client_data.get("name_en", "client").replace(" ", "_")
    filename = f"intake_form_{safe_name}_{timestamp}.pdf"
    output_path = output_dir / filename

    generate_intake_form(client_data, matter_data, output_path)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="intake-bot",
        summary=f"Intake form generated for {client_data.get('name_en', 'Unknown')}",
    )

    return FileResponse(
        path=str(output_path),
        media_type="application/pdf",
        filename=filename,
    )


@router.post("/generate-engagement-letter/{matter_id}")
async def generate_engagement_letter_route(request: Request, matter_id: int) -> FileResponse:
    db = _db(request)

    with get_db(db) as conn:
        matter_row = conn.execute(
            """SELECT m.*, c.name_en, c.name_tc, c.phone, c.email,
                      c.hkid_last4, c.source_channel
               FROM matters m
               JOIN clients c ON c.id = m.client_id
               WHERE m.id = ?""",
            (matter_id,),
        ).fetchone()

        if not matter_row:
            raise HTTPException(status_code=404, detail="Matter not found")

    row = dict(matter_row)

    client_data = {
        "name_en": row["name_en"],
        "name_tc": row["name_tc"],
        "phone": row["phone"],
        "email": row["email"],
    }
    matter_data = {
        "matter_type": row["matter_type"],
        "description": row["description"],
        "adverse_party_name": row["adverse_party_name"],
        "adverse_party_name_tc": row["adverse_party_name_tc"],
        "urgency": row["urgency"],
        "assigned_solicitor": row["assigned_solicitor"],
    }

    config = request.app.state.config
    firm_config = {
        "firm_name": config.extra.get("firm_name", "Law Firm"),
        "hkls_registration": config.extra.get("hkls_registration", ""),
        "office_address": config.extra.get("office_address", ""),
        "default_fee_type": config.extra.get("default_fee_type", "hourly"),
        "hourly_rate": config.extra.get("hourly_rate", "HK$3,000 – HK$6,000"),
    }

    workspace = request.app.state.workspace
    output_dir = workspace / "generated" / "engagement_letters"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = client_data.get("name_en", "client").replace(" ", "_")
    filename = f"engagement_letter_{safe_name}_{timestamp}.docx"
    output_path = output_dir / filename

    generate_engagement_letter(client_data, matter_data, firm_config, output_path)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="intake-bot",
        summary=f"Engagement letter drafted for matter #{matter_id} ({client_data.get('name_en', 'Unknown')})",
    )

    return FileResponse(
        path=str(output_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=filename,
    )


# ── Messaging webhooks ────────────────────────────────────────────────────


@router.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request) -> HTMLResponse:
    db = _db(request)
    form_data = dict(await request.form())
    twiml = handle_whatsapp_message(form_data, db, llm=request.app.state.llm)
    return HTMLResponse(content=twiml, media_type="application/xml")


@router.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict[str, Any]:
    db = _db(request)
    update = await request.json()
    result = handle_telegram_update(update, db, llm=request.app.state.llm)

    config = request.app.state.config
    tg_config = {
        "telegram_bot_token": config.messaging.telegram_bot_token,
    }

    from legal.intake_bot.bot.telegram import send_telegram_message
    await send_telegram_message(result["chat_id"], result["text"], tg_config)

    return {"ok": True}


# ── HTMX partials ─────────────────────────────────────────────────────────


@router.get("/client-form/partial", response_class=HTMLResponse)
async def partial_client_form(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "intake_bot/partials/client_form.html",
        {"request": request},
    )


@router.get("/conflict-panel/partial", response_class=HTMLResponse)
async def partial_conflict_panel(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        matters = [dict(r) for r in conn.execute(
            """SELECT m.id, m.matter_type, m.adverse_party_name, c.name_en as client_name
               FROM matters m
               JOIN clients c ON c.id = m.client_id
               WHERE m.status IN ('intake', 'active')
               ORDER BY m.created_date DESC LIMIT 20"""
        ).fetchall()]

    return templates.TemplateResponse(
        "intake_bot/partials/conflict_panel.html",
        {"request": request, "matters": matters},
    )


@router.get("/meeting-scheduler/partial", response_class=HTMLResponse)
async def partial_meeting_scheduler(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        clients = [dict(r) for r in conn.execute(
            "SELECT id, name_en FROM clients WHERE status != 'rejected' ORDER BY name_en"
        ).fetchall()]

        appointments = [dict(r) for r in conn.execute(
            """SELECT a.*, c.name_en as client_name
               FROM appointments a
               JOIN clients c ON c.id = a.client_id
               WHERE a.status IN ('scheduled', 'confirmed')
               ORDER BY a.datetime ASC LIMIT 20"""
        ).fetchall()]

    solicitors = _get_solicitors(request)

    return templates.TemplateResponse(
        "intake_bot/partials/meeting_scheduler.html",
        {
            "request": request,
            "clients": clients,
            "appointments": appointments,
            "solicitors": solicitors,
        },
    )


def _get_solicitors(request: Request) -> list[str]:
    """Extract solicitor names from config or DB."""
    config = request.app.state.config
    practice_areas = config.extra.get("practice_areas", "")
    if practice_areas:
        return [s.strip() for s in practice_areas.split(",") if s.strip()]
    return ["J. Lee", "A. Ho"]
