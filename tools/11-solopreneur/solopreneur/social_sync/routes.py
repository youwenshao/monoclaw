"""SocialSync FastAPI routes — social media distribution for HK solopreneurs."""

from __future__ import annotations

import json
import shutil
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

router = APIRouter(prefix="/social-sync", tags=["SocialSync"])

templates = Jinja2Templates(directory="solopreneur/dashboard/templates")


def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "social-sync",
        **extra,
    }


# ── Main Page ──────────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def social_sync_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["socialsync"]
    now = datetime.now()
    week_start = (now.date().isoformat())

    with get_db(db) as conn:
        posts_this_week = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE created_at >= ? AND status = 'published'",
            (week_start,),
        ).fetchone()[0]
        scheduled_count = conn.execute(
            "SELECT COUNT(*) FROM posts WHERE status = 'scheduled'"
        ).fetchone()[0]
        reach_row = conn.execute(
            """SELECT COALESCE(SUM(a.reach), 0) FROM analytics a
               JOIN platform_posts pp ON pp.id = a.platform_post_id
               JOIN posts p ON p.id = pp.post_id
               WHERE p.created_at >= ?""",
            (week_start,),
        ).fetchone()
        total_reach = reach_row[0] if reach_row else 0
        eng_row = conn.execute(
            """SELECT
                 COALESCE(SUM(a.likes + a.comments + a.shares + a.saves), 0) AS engagement,
                 COALESCE(SUM(a.reach), 0) AS reach
               FROM analytics a
               JOIN platform_posts pp ON pp.id = a.platform_post_id
               JOIN posts p ON p.id = pp.post_id
               WHERE p.created_at >= ?""",
            (week_start,),
        ).fetchone()
        engagement = eng_row[0] if eng_row else 0
        reach_for_rate = eng_row[1] if eng_row else 0
        engagement_rate = round(engagement / reach_for_rate * 100, 1) if reach_for_rate else 0.0

    return templates.TemplateResponse(
        "social_sync/index.html",
        _ctx(
            request,
            posts_this_week=posts_this_week,
            scheduled_count=scheduled_count,
            total_reach=total_reach,
            engagement_rate=engagement_rate,
        ),
    )


# ── Partials ───────────────────────────────────────────────────────────────

@router.get("/partials/post-composer", response_class=HTMLResponse)
async def post_composer_partial(request: Request) -> HTMLResponse:
    from solopreneur.social_sync.scheduling.optimal_times import get_next_optimal_time

    next_time = get_next_optimal_time()
    return templates.TemplateResponse(
        "social_sync/partials/post_composer.html",
        _ctx(request, suggested_time=next_time.strftime("%Y-%m-%dT%H:%M")),
    )


@router.get("/partials/content-calendar", response_class=HTMLResponse)
async def content_calendar_partial(
    request: Request,
    year: int | None = None,
    month: int | None = None,
) -> HTMLResponse:
    from solopreneur.social_sync.scheduling.calendar_manager import (
        get_calendar,
        seed_hk_events,
    )

    db = request.app.state.db_paths["socialsync"]
    now = datetime.now()
    y = year or now.year
    m = month or now.month

    seed_hk_events(db, y)
    entries = get_calendar(db, y, m)

    return templates.TemplateResponse(
        "social_sync/partials/content_calendar.html",
        _ctx(request, entries=entries, year=y, month=m),
    )


@router.get("/partials/platform-connections", response_class=HTMLResponse)
async def platform_connections_partial(request: Request) -> HTMLResponse:
    config = request.app.state.config
    connections = {
        "instagram": bool(config.extra.get("instagram_access_token")),
        "facebook": bool(config.extra.get("facebook_access_token")),
        "whatsapp": bool(config.messaging.twilio_account_sid),
    }
    return templates.TemplateResponse(
        "social_sync/partials/platform_connections.html",
        _ctx(request, connections=connections),
    )


@router.get("/partials/engagement-analytics", response_class=HTMLResponse)
async def engagement_analytics_partial(request: Request) -> HTMLResponse:
    from solopreneur.social_sync.analytics.report_generator import (
        generate_weekly_report,
    )

    db = request.app.state.db_paths["socialsync"]
    report = generate_weekly_report(db)

    return templates.TemplateResponse(
        "social_sync/partials/engagement_analytics.html",
        _ctx(request, report=report),
    )


# ── Post CRUD ──────────────────────────────────────────────────────────────

class CreatePostRequest(BaseModel):
    content_text: str
    content_text_tc: str | None = None
    image_paths: list[str] | None = None
    video_path: str | None = None
    hashtags: list[str] | None = None
    cta_text: str | None = None
    cta_link: str | None = None
    platforms: list[str] = []
    scheduled_time: str | None = None


@router.post("/posts")
async def create_post(request: Request, body: CreatePostRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["socialsync"]
    status = "scheduled" if body.scheduled_time else "draft"

    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO posts
               (content_text, content_text_tc, image_paths, video_path,
                hashtags, cta_text, cta_link, scheduled_time, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                body.content_text,
                body.content_text_tc,
                json.dumps(body.image_paths or []),
                body.video_path,
                json.dumps(body.hashtags or []),
                body.cta_text,
                body.cta_link,
                body.scheduled_time,
                status,
            ),
        )
        post_id = cursor.lastrowid

        for platform in body.platforms:
            conn.execute(
                """INSERT INTO platform_posts (post_id, platform, publish_status)
                   VALUES (?, ?, 'pending')""",
                (post_id, platform),
            )

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="social-sync",
        summary=f"Post #{post_id} created ({status}) for {', '.join(body.platforms)}",
    )

    return {"post_id": post_id, "status": status}


@router.post("/posts/{post_id}/publish")
async def publish_post_now(request: Request, post_id: int) -> dict[str, Any]:
    db = request.app.state.db_paths["socialsync"]
    config = request.app.state.config

    with get_db(db) as conn:
        post_row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not post_row:
        raise HTTPException(status_code=404, detail="Post not found")

    post_data = dict(post_row)
    with get_db(db) as conn:
        platforms = [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM platform_posts WHERE post_id = ? AND publish_status = 'pending'",
                (post_id,),
            ).fetchall()
        ]

    if not platforms:
        raise HTTPException(status_code=400, detail="No pending platforms for this post")

    publishers: dict[str, Any] = {}
    ig_token = config.extra.get("instagram_access_token", "")
    ig_id = config.extra.get("instagram_business_id", "")
    fb_token = config.extra.get("facebook_access_token", "")
    fb_page = config.extra.get("facebook_page_id", "")

    for pp in platforms:
        plat = pp["platform"]
        if plat.startswith("instagram") and ig_token and ig_id:
            from solopreneur.social_sync.publishing.instagram_publisher import InstagramPublisher
            publishers[plat] = InstagramPublisher(ig_token, ig_id)
        elif plat.startswith("facebook") and fb_token and fb_page:
            from solopreneur.social_sync.publishing.facebook_publisher import FacebookPublisher
            publishers[plat] = FacebookPublisher(fb_page, fb_token)
        elif plat == "whatsapp_status":
            from solopreneur.social_sync.publishing.whatsapp_status import WhatsAppStatusPublisher
            publishers[plat] = WhatsAppStatusPublisher(None, config.messaging.twilio_whatsapp_from or "")

    if not publishers:
        raise HTTPException(
            status_code=400,
            detail="No platform credentials configured. Check Settings.",
        )

    from solopreneur.social_sync.publishing.multi_publisher import publish_to_all

    result = await publish_to_all(post_data, publishers, db)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="social-sync",
        summary=(
            f"Post #{post_id} published: "
            f"{result['summary']['succeeded']} ok, "
            f"{result['summary']['failed']} failed"
        ),
    )

    return result


@router.delete("/posts/{post_id}")
async def delete_post(request: Request, post_id: int) -> dict[str, str]:
    db = request.app.state.db_paths["socialsync"]

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Post not found")

    with get_db(db) as conn:
        conn.execute("DELETE FROM platform_posts WHERE post_id = ?", (post_id,))
        conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="social-sync",
        summary=f"Post #{post_id} deleted",
    )

    return {"status": "deleted", "post_id": str(post_id)}


# ── Media Upload ───────────────────────────────────────────────────────────

@router.post("/media/upload")
async def upload_media(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    workspace = request.app.state.workspace
    upload_dir = workspace / "uploads" / "social_sync"
    upload_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename or "upload").suffix
    filename = f"{uuid.uuid4().hex}{ext}"
    dest = upload_dir / filename

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    return {"path": str(dest), "filename": filename}


# ── Analytics ──────────────────────────────────────────────────────────────

@router.get("/analytics/weekly")
async def weekly_analytics(request: Request) -> dict[str, Any]:
    from solopreneur.social_sync.analytics.report_generator import generate_weekly_report

    db = request.app.state.db_paths["socialsync"]
    return generate_weekly_report(db)


# ── Hashtag Suggestions ───────────────────────────────────────────────────

@router.get("/hashtags/suggest")
async def suggest_hashtags(
    request: Request,
    text: str = "",
    category: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    from solopreneur.social_sync.content.caption_optimizer import suggest_hashtags as _suggest

    db = request.app.state.db_paths["socialsync"]
    tags = _suggest(text, category, db, limit=limit)
    return {"hashtags": tags}
