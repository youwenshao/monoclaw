"""GrantTracker FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/grant-tracker", tags=["GrantTracker"])

templates = Jinja2Templates(directory="academic/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "grant-tracker", **extra}


def _db(request: Request) -> Path:
    return request.app.state.db_paths["grant_tracker"]


def _mona_db(request: Request) -> Path:
    return request.app.state.db_paths["mona_events"]


# ── Main page ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def grant_tracker_page(request: Request) -> HTMLResponse:
    db = _db(request)

    from academic.grant_tracker.monitoring.deadline_aggregator import get_upcoming_deadlines
    from academic.grant_tracker.applications.submission_tracker import get_applications

    deadlines = get_upcoming_deadlines(db, days_ahead=90)
    applications = get_applications(db)

    active_apps = [a for a in applications if a["status"] not in ("awarded", "rejected", "withdrawn")]
    total_awarded = sum((a.get("awarded_amount") or 0) for a in applications if a["status"] == "awarded")

    with get_db(db) as conn:
        pub_count = conn.execute("SELECT COUNT(*) FROM publications").fetchone()[0]

    return templates.TemplateResponse(
        "grant_tracker/index.html",
        _ctx(
            request,
            upcoming_count=len(deadlines),
            active_count=len(active_apps),
            total_awarded=total_awarded,
            pub_count=pub_count,
        ),
    )


# ── Deadlines ──────────────────────────────────────────────────────────────

@router.get("/deadlines")
async def list_deadlines(request: Request) -> list[dict]:
    from academic.grant_tracker.monitoring.deadline_aggregator import get_upcoming_deadlines
    return get_upcoming_deadlines(_db(request), days_ahead=365)


@router.post("/deadlines")
async def add_deadline(request: Request) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    with get_db(db) as conn:
        scheme_id = body.get("scheme_id")
        if not scheme_id:
            raise HTTPException(status_code=400, detail="scheme_id is required")

        cur = conn.execute(
            """INSERT INTO deadlines (scheme_id, year, external_deadline, institutional_deadline, call_url, status, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                scheme_id,
                body.get("year"),
                body.get("external_deadline"),
                body.get("institutional_deadline"),
                body.get("call_url"),
                body.get("status", "upcoming"),
                body.get("notes", ""),
            ),
        )
        deadline_id = cur.lastrowid

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="grant-tracker",
        summary=f"Deadline #{deadline_id} added for scheme {scheme_id}",
    )

    return {"deadline_id": deadline_id, "status": "created"}


@router.post("/scrape")
async def scrape_deadlines(request: Request) -> dict[str, Any]:
    db = _db(request)

    from academic.grant_tracker.monitoring.rgc_monitor import scrape_rgc_deadlines
    from academic.grant_tracker.monitoring.itf_monitor import scrape_itf_deadlines
    from academic.grant_tracker.monitoring.deadline_aggregator import aggregate_deadlines

    scraped: list[dict] = []
    try:
        scraped.extend(scrape_rgc_deadlines())
    except Exception:
        pass
    try:
        scraped.extend(scrape_itf_deadlines())
    except Exception:
        pass

    deadlines = aggregate_deadlines(db, scraped=scraped)

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="grant-tracker",
        summary=f"Scraped {len(scraped)} deadline entries, {len(deadlines)} total in DB",
    )

    return {"scraped": len(scraped), "total": len(deadlines)}


# ── Applications ───────────────────────────────────────────────────────────

@router.get("/applications")
async def list_applications(request: Request, status: str | None = None) -> list[dict]:
    from academic.grant_tracker.applications.submission_tracker import get_applications
    return get_applications(_db(request), status=status)


@router.post("/applications")
async def create_application(request: Request) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    from academic.grant_tracker.applications.submission_tracker import create_application as _create

    required = ("researcher_id", "scheme_id", "deadline_id", "project_title")
    for field in required:
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"{field} is required")

    app_id = _create(
        db,
        researcher_id=body["researcher_id"],
        scheme_id=body["scheme_id"],
        deadline_id=body["deadline_id"],
        project_title=body["project_title"],
        requested_amount=body.get("requested_amount"),
        duration_months=body.get("duration_months"),
        notes=body.get("notes", ""),
    )

    emit_event(
        _mona_db(request),
        event_type="action_started",
        tool_name="grant-tracker",
        summary=f"Application #{app_id} created: {body['project_title']}",
    )

    return {"application_id": app_id, "status": "planning"}


@router.get("/applications/{app_id}")
async def get_application(request: Request, app_id: int) -> dict[str, Any]:
    from academic.grant_tracker.applications.submission_tracker import get_application_detail
    detail = get_application_detail(_db(request), app_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Application not found")
    return detail


@router.post("/applications/{app_id}/status")
async def update_application_status(request: Request, app_id: int) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()
    new_status = body.get("status")
    if not new_status:
        raise HTTPException(status_code=400, detail="status is required")

    from academic.grant_tracker.applications.submission_tracker import update_application_status as _update

    ok = _update(db, app_id, new_status, **{k: v for k, v in body.items() if k != "status"})
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid status transition")

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="grant-tracker",
        summary=f"Application #{app_id} → {new_status}",
        requires_human_action=new_status == "internal_review",
    )

    return {"application_id": app_id, "status": new_status}


# ── Budget ─────────────────────────────────────────────────────────────────

@router.get("/budget/{app_id}")
async def get_budget(request: Request, app_id: int) -> dict[str, Any]:
    from academic.grant_tracker.applications.budget_builder import get_budget_summary
    return get_budget_summary(_db(request), app_id)


@router.post("/budget/{app_id}")
async def add_budget_item(request: Request, app_id: int) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    for field in ("category", "amount"):
        if not body.get(field):
            raise HTTPException(status_code=400, detail=f"{field} is required")

    with get_db(db) as conn:
        row = conn.execute("SELECT id FROM applications WHERE id = ?", (app_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Application not found")

        cur = conn.execute(
            """INSERT INTO budget_items (application_id, category, description, year, amount, justification)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (app_id, body["category"], body.get("description", ""), body.get("year"), body["amount"], body.get("justification", "")),
        )
        item_id = cur.lastrowid

    return {"budget_item_id": item_id, "application_id": app_id}


# ── Researchers ────────────────────────────────────────────────────────────

@router.get("/researchers")
async def list_researchers(request: Request) -> list[dict]:
    with get_db(_db(request)) as conn:
        rows = conn.execute("SELECT * FROM researchers ORDER BY name_en").fetchall()
    return [dict(r) for r in rows]


@router.post("/researchers")
async def create_researcher_endpoint(request: Request) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    if not body.get("name_en"):
        raise HTTPException(status_code=400, detail="name_en is required")

    from academic.grant_tracker.profile.researcher_profile import create_researcher

    rid = create_researcher(db, name_en=body["name_en"], name_tc=body.get("name_tc", ""), **{
        k: v for k, v in body.items() if k not in ("name_en", "name_tc")
    })

    return {"researcher_id": rid}


# ── Publications ───────────────────────────────────────────────────────────

@router.get("/publications")
async def list_publications(request: Request) -> list[dict]:
    with get_db(_db(request)) as conn:
        rows = conn.execute(
            "SELECT * FROM publications ORDER BY year DESC, citation_count DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@router.post("/publications")
async def add_publication(request: Request) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    with get_db(db) as conn:
        cur = conn.execute(
            """INSERT INTO publications
               (researcher_id, title, authors, journal, year, doi, citation_count, is_corresponding_author)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.get("researcher_id"),
                body.get("title", ""),
                body.get("authors", ""),
                body.get("journal", ""),
                body.get("year"),
                body.get("doi"),
                body.get("citation_count", 0),
                body.get("is_corresponding_author", False),
            ),
        )
        pub_id = cur.lastrowid

    return {"publication_id": pub_id}


@router.post("/publications/fetch")
async def fetch_publications(request: Request) -> dict[str, Any]:
    db = _db(request)
    body = await request.json()

    from academic.grant_tracker.profile.scholar_fetcher import fetch_publications as _fetch

    papers = _fetch(
        author_name=body.get("author_name", ""),
        semantic_scholar_id=body.get("semantic_scholar_id", ""),
    )

    researcher_id = body.get("researcher_id")
    inserted = 0
    with get_db(db) as conn:
        for p in papers:
            existing = None
            if p.get("doi"):
                existing = conn.execute("SELECT id FROM publications WHERE doi = ?", (p["doi"],)).fetchone()
            if not existing:
                conn.execute(
                    """INSERT INTO publications
                       (researcher_id, title, authors, journal, year, doi, citation_count, is_corresponding_author)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (researcher_id, p["title"], p["authors"], p["journal"], p["year"], p.get("doi"), p.get("citation_count", 0), False),
                )
                inserted += 1

    emit_event(
        _mona_db(request),
        event_type="action_completed",
        tool_name="grant-tracker",
        summary=f"Fetched {len(papers)} publications from Semantic Scholar, {inserted} new",
    )

    return {"fetched": len(papers), "inserted": inserted}


# ── Calendar events (FullCalendar JSON feed) ──────────────────────────────

@router.get("/calendar-events")
async def calendar_events(request: Request) -> list[dict]:
    from academic.grant_tracker.monitoring.deadline_aggregator import get_calendar_events
    return get_calendar_events(_db(request))


# ── HTMX Partials ─────────────────────────────────────────────────────────

@router.get("/partials/deadline-calendar", response_class=HTMLResponse)
async def partial_deadline_calendar(request: Request) -> HTMLResponse:
    from academic.grant_tracker.monitoring.deadline_aggregator import get_upcoming_deadlines
    deadlines = get_upcoming_deadlines(_db(request), days_ahead=180)
    return templates.TemplateResponse(
        "grant_tracker/partials/deadline_calendar.html",
        {"request": request, "deadlines": deadlines},
    )


@router.get("/partials/application-board", response_class=HTMLResponse)
async def partial_application_board(request: Request) -> HTMLResponse:
    from academic.grant_tracker.applications.submission_tracker import get_applications
    applications = get_applications(_db(request))
    return templates.TemplateResponse(
        "grant_tracker/partials/application_board.html",
        {"request": request, "applications": applications},
    )


@router.get("/partials/budget-calculator", response_class=HTMLResponse)
async def partial_budget_calculator(request: Request, app_id: int = 0) -> HTMLResponse:
    from academic.grant_tracker.applications.budget_builder import get_budget_summary

    summary = get_budget_summary(_db(request), app_id) if app_id else {
        "by_category": {}, "by_year": {}, "by_category_year": {}, "grand_total": 0, "items": [],
    }

    with get_db(_db(request)) as conn:
        applications = [dict(r) for r in conn.execute(
            "SELECT id, project_title FROM applications ORDER BY created_at DESC"
        ).fetchall()]

    return templates.TemplateResponse(
        "grant_tracker/partials/budget_calculator.html",
        {"request": request, "summary": summary, "app_id": app_id, "applications": applications},
    )


@router.get("/partials/publication-list", response_class=HTMLResponse)
async def partial_publication_list(request: Request) -> HTMLResponse:
    with get_db(_db(request)) as conn:
        publications = [dict(r) for r in conn.execute(
            "SELECT * FROM publications ORDER BY year DESC, citation_count DESC"
        ).fetchall()]
        researchers = [dict(r) for r in conn.execute(
            "SELECT id, name_en FROM researchers ORDER BY name_en"
        ).fetchall()]
    return templates.TemplateResponse(
        "grant_tracker/partials/publication_list.html",
        {"request": request, "publications": publications, "researchers": researchers},
    )
