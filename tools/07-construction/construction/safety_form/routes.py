"""SafetyForm Bot FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/safety-form", tags=["SafetyForm"])
templates = Jinja2Templates(directory="construction/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "safety-form", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["safety_form"]


# -- Request models ------------------------------------------------------------

class InspectionCreate(BaseModel):
    site_id: int
    inspector: str = ""
    weather: str = ""
    temperature: float | None = None
    worker_count: int | None = None


class ChecklistItemUpdate(BaseModel):
    status: str = "pass"
    notes: str = ""


class IncidentReport(BaseModel):
    site_id: int
    incident_type: str = "near_miss"
    location_on_site: str = ""
    description: str = ""
    persons_involved: str = ""
    injuries: str = ""
    immediate_action: str = ""


class ToolboxTalkCreate(BaseModel):
    site_id: int
    topic: str
    language: str = "en"
    conductor: str = ""
    attendee_count: int = 0
    attendee_names: str = ""
    duration_minutes: int = 15


# -- Page ----------------------------------------------------------------------

@router.get("/", response_class=HTMLResponse)
async def safety_form_page(request: Request) -> HTMLResponse:
    db = _db(request)

    with get_db(db) as conn:
        sites = [dict(r) for r in conn.execute(
            "SELECT * FROM sites WHERE status = 'active' ORDER BY site_name"
        ).fetchall()]
        today_inspections = [dict(r) for r in conn.execute(
            "SELECT di.*, s.site_name FROM daily_inspections di "
            "LEFT JOIN sites s ON di.site_id = s.id "
            "WHERE di.inspection_date = ? ORDER BY di.created_at DESC",
            (date.today().isoformat(),),
        ).fetchall()]
        open_deficiencies = conn.execute(
            "SELECT COUNT(*) FROM deficiencies WHERE status = 'open'"
        ).fetchone()[0]
        total_incidents = conn.execute(
            "SELECT COUNT(*) FROM incidents WHERE status = 'open'"
        ).fetchone()[0]
        month_start = date.today().replace(day=1).isoformat()
        month_talks = conn.execute(
            "SELECT COUNT(*) FROM toolbox_talks WHERE talk_date >= ?",
            (month_start,),
        ).fetchone()[0]

    return templates.TemplateResponse(
        "safety_form/index.html",
        _ctx(
            request,
            sites=sites,
            today_inspections=today_inspections,
            open_deficiencies=open_deficiencies,
            total_incidents=total_incidents,
            month_talks=month_talks,
        ),
    )


# -- Inspections ---------------------------------------------------------------

@router.post("/inspections")
async def create_inspection(request: Request, body: InspectionCreate) -> dict[str, Any]:
    db = _db(request)
    today = date.today().isoformat()
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO daily_inspections (site_id, inspection_date, inspector, weather, temperature, worker_count) "
            "VALUES (?,?,?,?,?,?)",
            (body.site_id, today, body.inspector, body.weather, body.temperature, body.worker_count),
        )
        inspection_id = cursor.lastrowid

        from construction.safety_form.inspections.checklist_engine import get_default_checklist
        items = get_default_checklist()
        for item in items:
            conn.execute(
                "INSERT INTO checklist_items (inspection_id, category, item_description) VALUES (?,?,?)",
                (inspection_id, item["category"], item["description"]),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="safety-form",
        summary=f"Daily inspection started for site #{body.site_id}",
    )
    return {"inspection_id": inspection_id}


@router.post("/inspections/{inspection_id}/items")
async def update_checklist_item(
    request: Request,
    inspection_id: int,
    item_id: int = Form(...),
    status: str = Form("pass"),
    notes: str = Form(""),
    photo: UploadFile | None = File(None),
) -> dict[str, Any]:
    db = _db(request)
    photo_path = None
    if photo and photo.filename:
        from construction.safety_form.inspections.photo_processor import save_inspection_photo
        photo_path = await save_inspection_photo(request.app.state.workspace, inspection_id, item_id, photo)

    with get_db(db) as conn:
        conn.execute(
            "UPDATE checklist_items SET status = ?, notes = ?, photo_path = COALESCE(?, photo_path) WHERE id = ? AND inspection_id = ?",
            (status, notes, photo_path, item_id, inspection_id),
        )

        if status == "fail":
            item = conn.execute("SELECT * FROM checklist_items WHERE id = ?", (item_id,)).fetchone()
            if item:
                insp = conn.execute("SELECT site_id FROM daily_inspections WHERE id = ?", (inspection_id,)).fetchone()
                if insp:
                    conn.execute(
                        "INSERT INTO deficiencies (site_id, category, description, severity, photo_path, reported_date, status) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (insp["site_id"], item["category"], item["item_description"], "minor",
                         photo_path, date.today().isoformat(), "open"),
                    )

    return {"item_id": item_id, "status": status}


@router.post("/inspections/{inspection_id}/complete")
async def complete_inspection(request: Request, inspection_id: int) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        items = conn.execute(
            "SELECT status FROM checklist_items WHERE inspection_id = ?",
            (inspection_id,),
        ).fetchall()
        if not items:
            raise HTTPException(status_code=404, detail="Inspection not found")
        total = len(items)
        passed = sum(1 for i in items if i["status"] == "pass")
        score = (passed / total * 100) if total else 0

        conn.execute(
            "UPDATE daily_inspections SET status = 'completed', overall_score = ?, completed_at = ? WHERE id = ?",
            (score, datetime.now().isoformat(), inspection_id),
        )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="safety-form",
        summary=f"Inspection #{inspection_id} completed — score: {score:.0f}%",
    )
    return {"inspection_id": inspection_id, "score": score}


# -- SSSS Reports -------------------------------------------------------------

@router.post("/reports/ssss")
async def generate_ssss_report(request: Request, site_id: int = Form(...), report_date: str = Form("")) -> dict[str, Any]:
    if not report_date:
        report_date = date.today().isoformat()

    from construction.safety_form.reporting.ssss_report import generate_ssss_pdf
    pdf_path = generate_ssss_pdf(
        _db(request), request.app.state.workspace, site_id, report_date,
    )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="safety-form",
        summary=f"SSSS report generated for site #{site_id} on {report_date}",
    )
    return {"pdf_path": str(pdf_path)}


# -- Toolbox Talks -------------------------------------------------------------

@router.post("/toolbox-talks")
async def create_toolbox_talk(request: Request, body: ToolboxTalkCreate) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO toolbox_talks (site_id, talk_date, topic, language, conductor, attendee_count, attendee_names, duration_minutes) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (body.site_id, date.today().isoformat(), body.topic, body.language,
             body.conductor, body.attendee_count, body.attendee_names, body.duration_minutes),
        )
    return {"talk_id": cursor.lastrowid}


# -- Incidents -----------------------------------------------------------------

@router.post("/incidents")
async def report_incident(request: Request, body: IncidentReport) -> dict[str, Any]:
    db = _db(request)
    with get_db(db) as conn:
        cursor = conn.execute(
            "INSERT INTO incidents (site_id, incident_type, date_time, location_on_site, description, "
            "persons_involved, injuries, immediate_action) VALUES (?,?,?,?,?,?,?,?)",
            (body.site_id, body.incident_type, datetime.now().isoformat(), body.location_on_site,
             body.description, body.persons_involved, body.injuries, body.immediate_action),
        )
        incident_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="alert",
        tool_name="safety-form",
        summary=f"Incident reported at site #{body.site_id}: {body.incident_type}",
        requires_human_action=True,
    )
    return {"incident_id": incident_id}


# -- WhatsApp webhook ----------------------------------------------------------

@router.post("/webhook")
async def whatsapp_webhook(request: Request) -> dict[str, str]:
    from construction.safety_form.bot.whatsapp_handler import handle_incoming
    form = await request.form()
    await handle_incoming(dict(form), request.app.state)
    return {"status": "ok"}


# -- Partials ------------------------------------------------------------------

@router.get("/partials/checklist", response_class=HTMLResponse)
async def checklist_partial(request: Request, inspection_id: int) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        items = [dict(r) for r in conn.execute(
            "SELECT * FROM checklist_items WHERE inspection_id = ? ORDER BY category, id",
            (inspection_id,),
        ).fetchall()]
    return templates.TemplateResponse(
        "safety_form/partials/daily_checklist.html",
        {"request": request, "items": items, "inspection_id": inspection_id},
    )


@router.get("/partials/ssss", response_class=HTMLResponse)
async def ssss_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        sites = [dict(r) for r in conn.execute("SELECT * FROM sites WHERE status = 'active'").fetchall()]
    return templates.TemplateResponse(
        "safety_form/partials/ssss_report.html",
        {"request": request, "sites": sites},
    )


@router.get("/partials/toolbox-talks", response_class=HTMLResponse)
async def toolbox_talks_partial(request: Request) -> HTMLResponse:
    db = _db(request)
    with get_db(db) as conn:
        talks = [dict(r) for r in conn.execute(
            "SELECT tt.*, s.site_name FROM toolbox_talks tt "
            "LEFT JOIN sites s ON tt.site_id = s.id ORDER BY tt.talk_date DESC LIMIT 20"
        ).fetchall()]
    return templates.TemplateResponse(
        "safety_form/partials/toolbox_talks.html",
        {"request": request, "talks": talks},
    )


@router.get("/partials/gallery", response_class=HTMLResponse)
async def photo_gallery_partial(request: Request, site_id: int | None = None) -> HTMLResponse:
    db = _db(request)
    query = (
        "SELECT ci.*, di.inspection_date, di.site_id FROM checklist_items ci "
        "LEFT JOIN daily_inspections di ON ci.inspection_id = di.id "
        "WHERE ci.photo_path IS NOT NULL"
    )
    params: list[Any] = []
    if site_id:
        query += " AND di.site_id = ?"
        params.append(site_id)
    query += " ORDER BY ci.photo_timestamp DESC LIMIT 50"

    with get_db(db) as conn:
        photos = [dict(r) for r in conn.execute(query, params).fetchall()]
    return templates.TemplateResponse(
        "safety_form/partials/photo_gallery.html",
        {"request": request, "photos": photos},
    )
