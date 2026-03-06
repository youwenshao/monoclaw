"""ListingSync FastAPI routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, field_validator

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from real_estate.listing_sync.processing.images import process_listing_images
from real_estate.listing_sync.processing.description import rewrite_description
from real_estate.listing_sync.tracking.lifecycle import update_listing_status
from real_estate.listing_sync.tracking.performance import get_performance_summary

router = APIRouter(prefix="/listing-sync", tags=["ListingSync"])

_BASE = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(_BASE / "dashboard" / "templates"))


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "listing-sync", **extra}


def _get_listings_with_platform_statuses(db_path: str | Path) -> list[dict]:
    with get_db(db_path) as conn:
        listings = [dict(r) for r in conn.execute(
            "SELECT * FROM listings ORDER BY updated_at DESC"
        ).fetchall()]
        for listing in listings:
            posts = conn.execute(
                "SELECT platform, status FROM platform_posts WHERE listing_id = ?",
                (listing["id"],),
            ).fetchall()
            listing["platform_statuses"] = {p["platform"]: p["status"] for p in posts}
    return listings


def _get_stats(db_path: str | Path) -> dict:
    with get_db(db_path) as conn:
        active = conn.execute(
            "SELECT COUNT(*) FROM listings WHERE status = 'active'"
        ).fetchone()[0]
        pending = conn.execute(
            "SELECT COUNT(*) FROM platform_posts WHERE status = 'pending'"
        ).fetchone()[0]
        total_views = conn.execute(
            "SELECT COALESCE(SUM(views), 0) FROM platform_posts"
        ).fetchone()[0] or 0
    return {"active_listings": active, "pending_syncs": pending, "total_views": total_views}


@router.get("/", response_class=HTMLResponse)
async def listing_sync_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["listing_sync"]
    listings = _get_listings_with_platform_statuses(db)
    stats = _get_stats(db)
    return templates.TemplateResponse(
        "listing_sync/index.html", _ctx(request, listings=listings, stats=stats)
    )


@router.get("/listings-table", response_class=HTMLResponse)
async def listings_table_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["listing_sync"]
    listings = _get_listings_with_platform_statuses(db)
    return templates.TemplateResponse(
        "listing_sync/_listings_table.html", _ctx(request, listings=listings)
    )


@router.get("/images-grid", response_class=HTMLResponse)
async def images_grid_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["listing_sync"]
    workspace = request.app.state.workspace
    with get_db(db) as conn:
        rows = conn.execute("""
            SELECT i.id, i.listing_id, i.original_path, i.processed_paths, i.watermarked, l.reference_code
            FROM images i
            JOIN listings l ON l.id = i.listing_id
            ORDER BY i.listing_id, i.sort_order, i.id
        """).fetchall()
    image_items = []
    for r in rows:
        d = dict(r)
        orig = d.get("original_path")
        proc = d.get("processed_paths") or ""
        # Resolve paths to URLs (simplified: use /static/ or file paths)
        d["original_url"] = f"/static/listing-images/{d['listing_id']}/{Path(orig).name}" if orig else None
        d["watermarked_url"] = None
        if d.get("watermarked") and proc:
            first = proc.split(",")[0].strip() if proc else None
            if first:
                d["watermarked_url"] = f"/static/listing-images/{d['listing_id']}/processed/{Path(first).name}"
        image_items.append(d)
    return templates.TemplateResponse(
        "listing_sync/_images_grid.html", _ctx(request, image_items=image_items)
    )


@router.get("/performance-section", response_class=HTMLResponse)
async def performance_section_partial(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["listing_sync"]
    performance = get_performance_summary(db)
    return templates.TemplateResponse(
        "listing_sync/_performance_section.html", _ctx(request, performance=performance)
    )


class CreateListingRequest(BaseModel):
    reference_code: str
    title_en: str | None = None
    title_zh: str | None = None
    description_master: str | None = None
    district: str | None = None
    estate: str | None = None
    address: str | None = None
    saleable_area_sqft: float | None = None
    gross_area_sqft: float | None = None
    price_hkd: int | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    floor: str | None = None
    facing: str | None = None

    @field_validator("saleable_area_sqft", "gross_area_sqft", mode="before")
    @classmethod
    def coerce_empty_float(cls, v: Any) -> float | None:
        if v is None or v == "":
            return None
        return float(v) if isinstance(v, (int, float, str)) else v

    @field_validator("price_hkd", "bedrooms", "bathrooms", mode="before")
    @classmethod
    def coerce_empty_int(cls, v: Any) -> int | None:
        if v is None or v == "":
            return None
        return int(float(v)) if isinstance(v, (int, float, str)) else v


@router.post("/listings")
async def create_listing(request: Request, listing: CreateListingRequest) -> dict[str, Any]:
    db = request.app.state.db_paths["listing_sync"]
    with get_db(db) as conn:
        cursor = conn.execute(
            """INSERT INTO listings
               (reference_code, title_en, title_zh, description_master, district,
                estate, address, saleable_area_sqft, gross_area_sqft, price_hkd,
                bedrooms, bathrooms, floor, facing)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (listing.reference_code, listing.title_en, listing.title_zh,
             listing.description_master, listing.district, listing.estate,
             listing.address, listing.saleable_area_sqft, listing.gross_area_sqft,
             listing.price_hkd, listing.bedrooms, listing.bathrooms,
             listing.floor, listing.facing),
        )
        listing_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="listing-sync",
        summary=f"New listing created: {listing.reference_code}",
    )
    return {"id": listing_id, "reference_code": listing.reference_code}


@router.put("/listings/{listing_id}")
async def update_listing(request: Request, listing_id: int, listing: CreateListingRequest) -> dict:
    db = request.app.state.db_paths["listing_sync"]
    with get_db(db) as conn:
        conn.execute(
            """UPDATE listings SET
               title_en=?, title_zh=?, description_master=?, district=?,
               estate=?, address=?, saleable_area_sqft=?, gross_area_sqft=?,
               price_hkd=?, bedrooms=?, bathrooms=?, floor=?, facing=?,
               updated_at=CURRENT_TIMESTAMP
               WHERE id=?""",
            (listing.title_en, listing.title_zh, listing.description_master,
             listing.district, listing.estate, listing.address,
             listing.saleable_area_sqft, listing.gross_area_sqft, listing.price_hkd,
             listing.bedrooms, listing.bathrooms, listing.floor, listing.facing,
             listing_id),
        )
    return {"id": listing_id, "status": "updated"}


@router.post("/listings/{listing_id}/sync")
async def sync_listing(request: Request, listing_id: int, platforms: list[str] | None = None) -> dict:
    db = request.app.state.db_paths["listing_sync"]
    llm = request.app.state.llm

    with get_db(db) as conn:
        row = conn.execute("SELECT * FROM listings WHERE id = ?", (listing_id,)).fetchone()
    if not row:
        return {"error": "Listing not found"}

    listing_data = dict(row)
    target_platforms = platforms or ["28hse", "squarefoot", "whatsapp"]
    results = {}

    for platform in target_platforms:
        desc = await rewrite_description(llm, listing_data, platform)
        with get_db(db) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO platform_posts
                   (listing_id, platform, description_adapted, status, posted_at)
                   VALUES (?, ?, ?, 'posted', CURRENT_TIMESTAMP)""",
                (listing_id, platform, desc),
            )
        results[platform] = {"status": "posted", "description_preview": desc[:100]}

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="listing-sync",
        summary=f"Listing {listing_data['reference_code']} synced to {', '.join(target_platforms)}",
    )
    return {"listing_id": listing_id, "results": results}


@router.post("/listings/{listing_id}/process-images")
async def process_images(request: Request, listing_id: int) -> dict:
    db = request.app.state.db_paths["listing_sync"]
    config = request.app.state.config
    workspace = request.app.state.workspace

    result = await process_listing_images(
        db, listing_id, workspace,
        eaa_license=config.extra.get("eaa_license", ""),
        watermark_opacity=config.extra.get("watermark_opacity", 0.6),
        watermark_font_size=config.extra.get("watermark_font_size", 14),
    )
    return result


@router.post("/listings/{listing_id}/status")
async def change_status(request: Request, listing_id: int, status: str = Form(...)) -> dict:
    db = request.app.state.db_paths["listing_sync"]
    result = update_listing_status(db, listing_id, status)
    return result


@router.get("/performance")
async def performance(request: Request) -> dict:
    db = request.app.state.db_paths["listing_sync"]
    return get_performance_summary(db)
