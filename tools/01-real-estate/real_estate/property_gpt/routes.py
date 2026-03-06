"""PropertyGPT FastAPI routes."""

from __future__ import annotations

import json
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

from real_estate.property_gpt.rag.retriever import search_buildings
from real_estate.property_gpt.rag.generator import generate_answer, stream_answer
from real_estate.property_gpt.rag.embedder import ingest_buildings
from real_estate.property_gpt.hk_utils import score_mtr_proximity, get_school_net_info
from real_estate.property_gpt.scrapers.building_db import get_comparable_transactions

router = APIRouter(prefix="/property-gpt", tags=["PropertyGPT"])

templates = Jinja2Templates(
    directory="real_estate/dashboard/templates"
)


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "property-gpt", **extra}


@router.get("/", response_class=HTMLResponse)
async def property_gpt_page(request: Request) -> HTMLResponse:
    db = request.app.state.db_paths["property_gpt"]
    with get_db(db) as conn:
        building_count = conn.execute("SELECT COUNT(*) FROM buildings").fetchone()[0]
        tx_count = conn.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        try:
            queries_today = conn.execute(
                "SELECT COUNT(*) FROM query_log WHERE date(timestamp) = date('now')"
            ).fetchone()[0]
        except Exception:
            queries_today = 0
    return templates.TemplateResponse(
        "property_gpt/index.html",
        _ctx(
            request,
            building_count=building_count,
            tx_count=tx_count,
            queries_today=queries_today,
        ),
    )


class SearchQuery(BaseModel):
    query: str
    district: str | None = None
    min_price: int | None = None
    max_price: int | None = None
    bedrooms: int | None = None
    limit: int = 10


@router.post("/search")
async def search(request: Request, q: SearchQuery) -> dict[str, Any]:
    start = time.time()
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["property_gpt"]

    results = await search_buildings(
        llm, db_path, q.query,
        district=q.district, min_price=q.min_price,
        max_price=q.max_price, limit=q.limit,
    )
    latency = int((time.time() - start) * 1000)
    return {"results": results, "latency_ms": latency, "total": len(results)}


class ChatQuery(BaseModel):
    query: str


@router.post("/chat")
async def chat(request: Request, q: ChatQuery) -> StreamingResponse:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["property_gpt"]

    async def stream():
        async for token in stream_answer(llm, db_path, q.query):
            yield token

    return StreamingResponse(stream(), media_type="text/plain")


class DescribeRequest(BaseModel):
    building_id: int
    flat: str | None = None
    floor: str | None = None
    platform: str = "general"


@router.post("/describe")
async def describe(request: Request, req: DescribeRequest) -> dict[str, str]:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["property_gpt"]

    with get_db(db_path) as conn:
        row = conn.execute("SELECT * FROM buildings WHERE id = ?", (req.building_id,)).fetchone()
    if not row:
        return {"error": "Building not found"}

    building = dict(row)
    description = await generate_answer(
        llm, db_path,
        f"Generate a {req.platform} listing description for: {building['name_en']} "
        f"({building['name_zh']}), {building['district']}. Describe the property.",
    )
    return {"description": description, "platform": req.platform}


class CompareRequest(BaseModel):
    building_ids: list[int]


@router.post("/compare")
async def compare(request: Request, req: CompareRequest) -> dict[str, Any]:
    db_path = request.app.state.db_paths["property_gpt"]
    buildings = []
    with get_db(db_path) as conn:
        for bid in req.building_ids:
            row = conn.execute("SELECT * FROM buildings WHERE id = ?", (bid,)).fetchone()
            if row:
                b = dict(row)
                b["mtr_grade"] = score_mtr_proximity(b.get("mtr_walk_minutes"))
                b["school_net_info"] = get_school_net_info(b.get("school_net"))
                buildings.append(b)
    return {"buildings": buildings, "count": len(buildings)}


@router.get("/trends")
async def trends(request: Request, district: str | None = None, days: int = 90) -> dict[str, Any]:
    db_path = request.app.state.db_paths["property_gpt"]
    txns = get_comparable_transactions(db_path, district=district, days=days)
    return {"transactions": txns, "district": district, "days": days}


# htmx partial endpoints

@router.get("/partials/search-results", response_class=HTMLResponse)
async def search_results_partial(
    request: Request,
    query: str = "",
    district: str = "",
    min_price: int | None = None,
    max_price: int | None = None,
    bedrooms: str = "",
) -> HTMLResponse:
    llm = request.app.state.llm
    db_path = request.app.state.db_paths["property_gpt"]
    results = await search_buildings(
        llm,
        db_path,
        query,
        district=district or None,
        min_price=min_price,
        max_price=max_price,
    )
    return templates.TemplateResponse(
        "property_gpt/partials/search_results.html",
        _ctx(request, results=results),
    )
