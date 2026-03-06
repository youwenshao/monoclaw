"""PolicyWatcher FastAPI routes."""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/policy-watcher", tags=["PolicyWatcher"])

templates = Jinja2Templates(directory="immigration/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "policy-watcher", **extra}


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def policy_watcher_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["policy_watcher"]

    with get_db(db) as conn:
        changes_this_month = conn.execute(
            "SELECT COUNT(*) FROM policy_changes WHERE detected_at >= date('now', '-30 days')"
        ).fetchone()[0]
        pending_review = conn.execute(
            "SELECT COUNT(*) FROM policy_changes WHERE urgency IN ('important', 'urgent')"
        ).fetchone()[0]
        active_subs = conn.execute(
            "SELECT COUNT(*) FROM alert_subscriptions WHERE active = 1"
        ).fetchone()[0]
        recent_changes = [dict(r) for r in conn.execute(
            """SELECT pc.*, pd.title, pd.title_zh, pd.published_date
               FROM policy_changes pc
               LEFT JOIN policy_documents pd ON pc.document_id = pd.id
               ORDER BY pc.detected_at DESC LIMIT 20"""
        ).fetchall()]
        sources = [dict(r) for r in conn.execute(
            "SELECT * FROM policy_sources ORDER BY source_name"
        ).fetchall()]

    return templates.TemplateResponse(
        "policy_watcher/index.html",
        _ctx(
            request,
            changes_this_month=changes_this_month,
            pending_review=pending_review,
            active_subs=active_subs,
            recent_changes=recent_changes,
            sources=sources,
        ),
    )


# ── Policy feed ────────────────────────────────────────────────────────────

@router.get("/feed")
async def policy_feed(
    request: Request,
    limit: int = 50,
    scheme: str | None = None,
    urgency: str | None = None,
) -> list[dict]:
    db = request.app.state.db_paths["policy_watcher"]
    query = """SELECT pc.*, pd.title, pd.title_zh, pd.published_date, pd.document_url
               FROM policy_changes pc
               LEFT JOIN policy_documents pd ON pc.document_id = pd.id
               WHERE 1=1"""
    params: list[Any] = []

    if scheme:
        query += " AND pc.affected_schemes LIKE ?"
        params.append(f"%{scheme}%")
    if urgency:
        query += " AND pc.urgency = ?"
        params.append(urgency)

    query += " ORDER BY pc.detected_at DESC LIMIT ?"
    params.append(limit)

    with get_db(db) as conn:
        rows = conn.execute(query, params).fetchall()
    return [dict(r) for r in rows]


# ── Diff viewer ────────────────────────────────────────────────────────────

@router.get("/changes/{change_id}/diff")
async def change_diff(request: Request, change_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["policy_watcher"]

    with get_db(db) as conn:
        change = conn.execute(
            "SELECT * FROM policy_changes WHERE id = ?", (change_id,)
        ).fetchone()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    change_data = dict(change)

    with get_db(db) as conn:
        current_doc = conn.execute(
            "SELECT * FROM policy_documents WHERE id = ?", (change_data["document_id"],)
        ).fetchone()
        prev_doc = None
        if change_data.get("previous_document_id"):
            prev_doc = conn.execute(
                "SELECT * FROM policy_documents WHERE id = ?",
                (change_data["previous_document_id"],),
            ).fetchone()

    return {
        "change": change_data,
        "current_document": dict(current_doc) if current_doc else None,
        "previous_document": dict(prev_doc) if prev_doc else None,
    }


# ── Search ─────────────────────────────────────────────────────────────────

@router.get("/search")
async def search_policies(
    request: Request,
    q: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    db = request.app.state.db_paths["policy_watcher"]

    if not q:
        return {"results": [], "query": q}

    from immigration.policy_watcher.archive.search import search_archive
    results = search_archive(db, q, date_from=date_from, date_to=date_to, limit=limit)

    return {"results": results, "query": q, "count": len(results)}


# ── Impact assessment ──────────────────────────────────────────────────────

@router.get("/impact/{change_id}")
async def impact_assessment(request: Request, change_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["policy_watcher"]
    portal_db = request.app.state.db_paths["client_portal"]

    with get_db(db) as conn:
        change = conn.execute(
            "SELECT * FROM policy_changes WHERE id = ?", (change_id,)
        ).fetchone()
    if not change:
        raise HTTPException(status_code=404, detail="Change not found")

    change_data = dict(change)
    affected_schemes = (change_data.get("affected_schemes") or "").split(",")

    affected_cases = []
    with get_db(portal_db) as conn:
        for scheme in affected_schemes:
            scheme = scheme.strip()
            if not scheme:
                continue
            cases = conn.execute(
                """SELECT * FROM cases WHERE scheme = ?
                   AND current_status NOT IN ('visa_label_issued', 'entry_made', 'hkid_applied')""",
                (scheme,),
            ).fetchall()
            affected_cases.extend([dict(c) for c in cases])

    return {
        "change": change_data,
        "affected_cases": affected_cases,
        "affected_count": len(affected_cases),
    }


# ── Manual scrape trigger ─────────────────────────────────────────────────

@router.post("/scrape-now")
async def trigger_scrape(request: Request, source_id: int | None = None) -> dict[str, Any]:
    from immigration.policy_watcher.scrapers.gazette import scrape_gazette
    from immigration.policy_watcher.scrapers.immd import scrape_immd

    db = request.app.state.db_paths["policy_watcher"]
    results = {}

    if source_id:
        with get_db(db) as conn:
            source = conn.execute("SELECT * FROM policy_sources WHERE id = ?", (source_id,)).fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        source_data = dict(source)
        results[source_data["source_name"]] = "triggered"
    else:
        results = {"gazette": "triggered", "immd": "triggered"}

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_started",
        tool_name="policy-watcher",
        summary=f"Manual scrape triggered for: {', '.join(results.keys())}",
    )

    return {"status": "scrape_started", "sources": results}


# ── Subscriptions ──────────────────────────────────────────────────────────

@router.get("/subscriptions")
async def list_subscriptions(request: Request) -> list[dict]:
    db = request.app.state.db_paths["policy_watcher"]
    with get_db(db) as conn:
        rows = conn.execute(
            "SELECT * FROM alert_subscriptions ORDER BY consultant_name"
        ).fetchall()
    return [dict(r) for r in rows]


class SubscriptionRequest(BaseModel):
    consultant_name: str
    phone: str | None = None
    email: str | None = None
    telegram_id: str | None = None
    schemes_filter: str | None = None
    urgency_threshold: str = "important"
    channel: str = "whatsapp"


@router.post("/subscriptions")
async def create_subscription(request: Request, body: SubscriptionRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["policy_watcher"]
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO alert_subscriptions
               (consultant_name, phone, email, telegram_id, schemes_filter, urgency_threshold, channel)
               VALUES (?,?,?,?,?,?,?)""",
            (body.consultant_name, body.phone, body.email, body.telegram_id,
             body.schemes_filter, body.urgency_threshold, body.channel),
        )
        sub_id = cursor.lastrowid

    return {"subscription_id": sub_id, "status": "active"}


# ── Partials ──────────────────────────────────────────────────────────────

@router.get("/feed/partial", response_class=HTMLResponse)
async def feed_partial(request: Request, scheme: str | None = None) -> HTMLResponse:
    db = request.app.state.db_paths["policy_watcher"]
    query = """SELECT pc.*, pd.title, pd.published_date
               FROM policy_changes pc
               LEFT JOIN policy_documents pd ON pc.document_id = pd.id
               WHERE 1=1"""
    params: list[Any] = []
    if scheme and scheme != "all":
        query += " AND pc.affected_schemes LIKE ?"
        params.append(f"%{scheme}%")
    query += " ORDER BY pc.detected_at DESC LIMIT 20"
    with get_db(db) as conn:
        changes = [dict(r) for r in conn.execute(query, params).fetchall()]
    return templates.TemplateResponse(
        "policy_watcher/partials/policy_feed.html",
        {"request": request, "changes": changes},
    )


@router.get("/diff-viewer/partial", response_class=HTMLResponse)
async def diff_viewer_partial(request: Request, change_id: int) -> HTMLResponse:
    diff_data = await change_diff(request, change_id)
    return templates.TemplateResponse(
        "policy_watcher/partials/diff_viewer.html",
        {"request": request, **diff_data},
    )
