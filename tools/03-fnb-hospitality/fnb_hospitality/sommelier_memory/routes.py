"""SommelierMemory FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from openclaw_shared.database import get_db

from fnb_hospitality.sommelier_memory.guests.profiles import (
    create_guest,
    delete_guest,
    get_guest,
    list_guests,
    search_guests,
    update_guest,
)
from fnb_hospitality.sommelier_memory.guests.preferences import (
    add_dietary_info,
    add_preference,
    get_dietary_info,
    get_preferences,
    remove_dietary_info,
)
from fnb_hospitality.sommelier_memory.guests.history import (
    calculate_lifetime_value,
    get_visit_history,
    log_visit,
)
from fnb_hospitality.sommelier_memory.guests.segments import (
    add_tag,
    refresh_all_tiers,
    remove_tag,
)
from fnb_hospitality.sommelier_memory.intelligence.briefing import (
    generate_briefing,
    generate_service_briefings,
)
from fnb_hospitality.sommelier_memory.intelligence.celebrations import (
    get_upcoming_celebrations,
)

router = APIRouter(prefix="/sommelier-memory", tags=["SommelierMemory"])

templates = Jinja2Templates(directory="fnb_hospitality/dashboard/templates")

HK_PHONE_PATTERN = r"^\+852[5679]\d{7}$"


# ── Pydantic request models ──────────────────────────────────────────────

class CreateGuestRequest(BaseModel):
    name: str
    phone: str
    preferred_name: str = ""
    email: str = ""
    photo_path: str = ""
    language_pref: str = "cantonese"
    tags: str = ""
    notes: str = ""

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        import re
        if not re.match(HK_PHONE_PATTERN, v.strip()):
            raise ValueError("Phone must be a valid HK number (+852XXXXXXXX)")
        return v.strip()


class UpdateGuestRequest(BaseModel):
    name: str | None = None
    preferred_name: str | None = None
    phone: str | None = None
    email: str | None = None
    photo_path: str | None = None
    language_pref: str | None = None
    tags: str | None = None
    notes: str | None = None


class DietaryInfoRequest(BaseModel):
    type: str
    item: str
    severity: str | None = None
    notes: str = ""


class PreferenceRequest(BaseModel):
    category: str
    preference: str
    strength: str = "like"
    notes: str = ""


class VisitRequest(BaseModel):
    visit_date: str
    party_size: int
    total_spend: float
    party_notes: str = ""
    table_number: str = ""
    wine_orders: str = ""
    food_highlights: str = ""
    staff_notes: str = ""
    rating: int | None = None


class TagRequest(BaseModel):
    tag: str


# ── Helpers ───────────────────────────────────────────────────────────────

def _ctx(request: Request, **extra: object) -> dict:
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": "sommelier-memory",
        **extra,
    }


def _db(request: Request) -> Path:
    return request.app.state.db_paths["sommelier_memory"]


def _mona(request: Request) -> Path:
    return request.app.state.db_paths["mona_events"]


# ── Dashboard page ────────────────────────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def sommelier_memory_page(request: Request) -> HTMLResponse:
    db = _db(request)

    guests = list_guests(db, limit=50)

    with get_db(db) as conn:
        total_guests = conn.execute("SELECT COUNT(*) FROM sm_guests").fetchone()[0]
        vip_count = conn.execute(
            "SELECT COUNT(*) FROM sm_guests WHERE vip_tier = 'vip'"
        ).fetchone()[0]
        vvip_count = conn.execute(
            "SELECT COUNT(*) FROM sm_guests WHERE vip_tier = 'vvip'"
        ).fetchone()[0]
        total_visits = conn.execute("SELECT COUNT(*) FROM visits").fetchone()[0]
        total_revenue = conn.execute(
            "SELECT COALESCE(SUM(total_spend), 0) FROM visits"
        ).fetchone()[0]

    celebrations = get_upcoming_celebrations(db, lookahead_days=7)

    return templates.TemplateResponse(
        "sommelier_memory/index.html",
        _ctx(
            request,
            guests=guests,
            total_guests=total_guests,
            vip_count=vip_count,
            vvip_count=vvip_count,
            total_visits=total_visits,
            total_revenue=total_revenue,
            celebrations=celebrations,
        ),
    )


# ── Guest CRUD ────────────────────────────────────────────────────────────

@router.get("/guests")
async def api_list_guests(
    request: Request,
    q: str = "",
    tags: str | None = None,
    vip_tier: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    db = _db(request)
    if q or tags or vip_tier:
        return search_guests(db, q, tags=tags, vip_tier=vip_tier)
    return list_guests(db, limit=limit, offset=offset)


@router.post("/guests")
async def api_create_guest(request: Request, body: CreateGuestRequest) -> dict[str, Any]:
    db = _db(request)
    try:
        return create_guest(
            db,
            body.name,
            body.phone,
            preferred_name=body.preferred_name,
            email=body.email,
            photo_path=body.photo_path,
            language_pref=body.language_pref,
            tags=body.tags,
            notes=body.notes,
            mona_db=_mona(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/guests/{guest_id}")
async def api_get_guest(request: Request, guest_id: int) -> dict[str, Any]:
    db = _db(request)
    guest = get_guest(db, guest_id)
    if not guest:
        raise HTTPException(status_code=404, detail="Guest not found")

    ltv = calculate_lifetime_value(db, guest_id)
    guest["lifetime_value"] = ltv
    return guest


@router.put("/guests/{guest_id}")
async def api_update_guest(
    request: Request,
    guest_id: int,
    body: UpdateGuestRequest,
) -> dict[str, Any]:
    db = _db(request)
    fields = body.model_dump(exclude_none=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        result = update_guest(db, guest_id, mona_db=_mona(request), **fields)
        if not result:
            raise HTTPException(status_code=404, detail="Guest not found")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/guests/{guest_id}")
async def api_delete_guest(request: Request, guest_id: int) -> dict[str, str]:
    db = _db(request)
    deleted = delete_guest(db, guest_id, mona_db=_mona(request))
    if not deleted:
        raise HTTPException(status_code=404, detail="Guest not found")
    return {"status": "deleted", "detail": "PDPO-compliant deletion completed"}


# ── Dietary info ──────────────────────────────────────────────────────────

@router.post("/guests/{guest_id}/dietary")
async def api_add_dietary(
    request: Request,
    guest_id: int,
    body: DietaryInfoRequest,
) -> dict[str, Any]:
    db = _db(request)
    try:
        return add_dietary_info(
            db, guest_id, body.type, body.item,
            severity=body.severity, notes=body.notes,
            mona_db=_mona(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/guests/{guest_id}/dietary/{info_id}")
async def api_remove_dietary(
    request: Request,
    guest_id: int,
    info_id: int,
) -> dict[str, Any]:
    db = _db(request)
    removed = remove_dietary_info(db, info_id, mona_db=_mona(request))
    if not removed:
        raise HTTPException(status_code=404, detail="Dietary info not found")
    return {"status": "removed", "info_id": info_id}


# ── Preferences ───────────────────────────────────────────────────────────

@router.post("/guests/{guest_id}/preferences")
async def api_add_preference(
    request: Request,
    guest_id: int,
    body: PreferenceRequest,
) -> dict[str, Any]:
    db = _db(request)
    try:
        return add_preference(
            db, guest_id, body.category, body.preference,
            strength=body.strength, notes=body.notes,
            mona_db=_mona(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Visit history ─────────────────────────────────────────────────────────

@router.post("/guests/{guest_id}/visits")
async def api_log_visit(
    request: Request,
    guest_id: int,
    body: VisitRequest,
) -> dict[str, Any]:
    db = _db(request)
    try:
        return log_visit(
            db, guest_id, body.visit_date, body.party_size, body.total_spend,
            party_notes=body.party_notes,
            table_number=body.table_number,
            wine_orders=body.wine_orders,
            food_highlights=body.food_highlights,
            staff_notes=body.staff_notes,
            rating=body.rating,
            mona_db=_mona(request),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/guests/{guest_id}/visits")
async def api_visit_history(
    request: Request,
    guest_id: int,
    limit: int = 20,
) -> list[dict[str, Any]]:
    db = _db(request)
    return get_visit_history(db, guest_id, limit=limit)


# ── Tags ──────────────────────────────────────────────────────────────────

@router.post("/guests/{guest_id}/tags")
async def api_add_tag(
    request: Request,
    guest_id: int,
    body: TagRequest,
) -> dict[str, Any]:
    db = _db(request)
    try:
        tags = add_tag(db, guest_id, body.tag, mona_db=_mona(request))
        return {"guest_id": guest_id, "tags": tags}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/guests/{guest_id}/tags/{tag}")
async def api_remove_tag(
    request: Request,
    guest_id: int,
    tag: str,
) -> dict[str, Any]:
    db = _db(request)
    try:
        tags = remove_tag(db, guest_id, tag, mona_db=_mona(request))
        return {"guest_id": guest_id, "tags": tags}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Briefings ─────────────────────────────────────────────────────────────

@router.get("/briefings/service/{service_date}")
async def api_service_briefings(request: Request, service_date: str) -> list[dict[str, Any]]:
    db = _db(request)
    llm = getattr(request.app.state, "llm", None)
    return await generate_service_briefings(db, service_date, llm_provider=llm)


@router.get("/briefings/{guest_id}")
async def api_guest_briefing(request: Request, guest_id: int) -> dict[str, Any]:
    db = _db(request)
    llm = getattr(request.app.state, "llm", None)
    try:
        return await generate_briefing(db, guest_id, llm_provider=llm)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Celebrations ──────────────────────────────────────────────────────────

@router.get("/celebrations/upcoming")
async def api_upcoming_celebrations(
    request: Request,
    days: int = 7,
) -> list[dict[str, Any]]:
    db = _db(request)
    return get_upcoming_celebrations(db, lookahead_days=days)


# ── HTMX Partials ────────────────────────────────────────────────────────

@router.get("/partials/guest-cards", response_class=HTMLResponse)
async def partial_guest_cards(
    request: Request,
    q: str = "",
    tags: str | None = None,
    vip_tier: str | None = None,
) -> HTMLResponse:
    db = _db(request)
    if q or tags or vip_tier:
        guests = search_guests(db, q, tags=tags, vip_tier=vip_tier)
    else:
        guests = list_guests(db, limit=50)

    return templates.TemplateResponse(
        "sommelier_memory/partials/guest_cards.html",
        {"request": request, "guests": guests},
    )


@router.get("/partials/celebration-calendar", response_class=HTMLResponse)
async def partial_celebration_calendar(
    request: Request,
    days: int = 7,
) -> HTMLResponse:
    db = _db(request)
    celebrations = get_upcoming_celebrations(db, lookahead_days=days)
    return templates.TemplateResponse(
        "sommelier_memory/partials/celebration_calendar.html",
        {"request": request, "celebrations": celebrations},
    )


@router.get("/partials/visit-timeline/{guest_id}", response_class=HTMLResponse)
async def partial_visit_timeline(
    request: Request,
    guest_id: int,
) -> HTMLResponse:
    db = _db(request)
    visits = get_visit_history(db, guest_id, limit=10)
    guest = get_guest(db, guest_id)
    ltv = calculate_lifetime_value(db, guest_id)
    return templates.TemplateResponse(
        "sommelier_memory/partials/visit_timeline.html",
        {"request": request, "visits": visits, "guest": guest, "lifetime_value": ltv},
    )


# ── Admin: Refresh tiers ─────────────────────────────────────────────────

@router.post("/admin/refresh-tiers")
async def api_refresh_tiers(request: Request) -> dict[str, Any]:
    db = _db(request)
    counts = refresh_all_tiers(db, mona_db=_mona(request))
    return {"status": "ok", "counts": counts}
