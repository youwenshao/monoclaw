"""HKDevKit FastAPI routes."""

from __future__ import annotations

import base64
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from openclaw_shared.database import get_db
from openclaw_shared.mona_events import emit_event

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

router = APIRouter(tags=["HKDevKit"])


def _ctx(request: Request, **extra: object) -> dict:
    return {"request": request, "config": request.app.state.config, "active_tab": "hk-dev-kit", **extra}


def _db(request: Request):
    return get_db(request.app.state.db_paths["hk_dev_kit"])


# ── Page ───────────────────────────────────────────────────────────────────

@router.get("/hk-dev-kit/", response_class=HTMLResponse)
async def hk_dev_kit_page(request: Request) -> HTMLResponse:
    with _db(request) as conn:
        snippet_count = conn.execute("SELECT COUNT(*) FROM snippets").fetchone()[0]
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
        api_configs = [dict(r) for r in conn.execute(
            "SELECT * FROM api_configs WHERE active = 1"
        ).fetchall()]

    return templates.TemplateResponse(
        "hk_dev_kit/index.html",
        _ctx(
            request,
            snippet_count=snippet_count,
            project_count=project_count,
            api_configs=api_configs,
        ),
    )


# ── FPS ────────────────────────────────────────────────────────────────────

class FPSQRRequest(BaseModel):
    proxy_id: str
    proxy_type: str = "mobile"
    amount: float
    currency: str = "HKD"
    reference: str = ""


@router.post("/api/hk-dev-kit/fps/qr")
async def generate_fps_qr(request: Request, body: FPSQRRequest) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.fps.fps_types import FPSPaymentRequest, FPSProxyType
    from vibe_coder.hk_dev_kit.connectors.fps.qr_generator import FPSQRGenerator

    payment = FPSPaymentRequest(
        proxy_id=body.proxy_id,
        proxy_type=FPSProxyType(body.proxy_type),
        amount=body.amount,
        currency=body.currency,
        reference=body.reference,
    )
    qr_bytes = FPSQRGenerator().generate(payment)
    qr_b64 = base64.b64encode(qr_bytes).decode()

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="hk-dev-kit",
        summary=f"FPS QR generated for {body.proxy_id} ({body.amount} {body.currency})",
    )

    return {"qr_base64": qr_b64, "proxy_id": body.proxy_id, "amount": body.amount}


class FPSPaymentBody(BaseModel):
    proxy_id: str
    proxy_type: str = "mobile"
    amount: float
    currency: str = "HKD"
    reference: str = ""


@router.post("/api/hk-dev-kit/fps/payment")
async def initiate_fps_payment(request: Request, body: FPSPaymentBody) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.fps.fps_types import FPSPaymentRequest, FPSProxyType
    from vibe_coder.hk_dev_kit.connectors.fps.payment_client import FPSPaymentClient

    payment = FPSPaymentRequest(
        proxy_id=body.proxy_id,
        proxy_type=FPSProxyType(body.proxy_type),
        amount=body.amount,
        currency=body.currency,
        reference=body.reference,
    )
    client = FPSPaymentClient()
    result = await client.initiate_payment(payment)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="hk-dev-kit",
        summary=f"FPS payment initiated: {result.transaction_id} ({body.amount} {body.currency})",
    )

    return {
        "transaction_id": result.transaction_id,
        "status": result.status,
        "qr_base64": base64.b64encode(result.qr_data).decode() if result.qr_data else None,
    }


# ── Octopus ────────────────────────────────────────────────────────────────

class OctopusPaymentBody(BaseModel):
    merchant_id: str = ""
    amount: float
    reference: str = ""


@router.post("/api/hk-dev-kit/octopus/payment")
async def octopus_payment(request: Request, body: OctopusPaymentBody) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.octopus.merchant_client import OctopusMerchantClient
    from vibe_coder.hk_dev_kit.connectors.octopus.octopus_types import OctopusPaymentRequest

    merchant_id = body.merchant_id or request.app.state.config.extra.get("octopus_merchant_id", "DEMO")
    req = OctopusPaymentRequest(
        merchant_id=merchant_id,
        amount=body.amount,
        reference=body.reference,
    )
    client = OctopusMerchantClient()
    txn = await client.create_payment(req)

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="hk-dev-kit",
        summary=f"Octopus payment: {txn.transaction_id} ({body.amount} HKD)",
    )

    return {
        "transaction_id": txn.transaction_id,
        "status": txn.status,
        "amount": txn.amount,
    }


# ── GovHK ──────────────────────────────────────────────────────────────────

@router.get("/api/hk-dev-kit/govhk/weather")
async def govhk_weather(request: Request, lang: str = "en") -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.govhk.weather import HKWeatherClient

    client = HKWeatherClient()
    weather = await client.get_current_weather(lang=lang)
    forecast = await client.get_forecast()
    warnings = await client.get_warnings()

    return {
        "current": {
            "temperature": weather.temperature,
            "humidity": weather.humidity,
            "uvindex": weather.uvindex,
            "description_en": weather.description_en,
            "description_zh": weather.description_zh,
            "update_time": weather.update_time,
        },
        "forecast_days": len(forecast.days),
        "active_warnings": len(warnings),
    }


@router.get("/api/hk-dev-kit/govhk/transport")
async def govhk_transport(request: Request, query_type: str = "mtr_lines") -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.govhk.transport import HKTransportClient

    client = HKTransportClient()

    if query_type == "mtr_lines":
        lines = await client.get_mtr_lines()
        return {"type": "mtr_lines", "data": [asdict(l) for l in lines]}

    if query_type == "bus_routes":
        routes = await client.get_bus_routes()
        return {"type": "bus_routes", "count": len(routes), "data": [asdict(r) for r in routes[:50]]}

    return {"error": f"Unknown query_type: {query_type}"}


# ── Validators ─────────────────────────────────────────────────────────────

class HKIDValidateBody(BaseModel):
    hkid: str


@router.post("/api/hk-dev-kit/validate/hkid")
async def validate_hkid_endpoint(request: Request, body: HKIDValidateBody) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.common.hkid_validator import validate_hkid

    valid = validate_hkid(body.hkid)
    return {"hkid": body.hkid, "valid": valid}


class PhoneValidateBody(BaseModel):
    phone: str


@router.post("/api/hk-dev-kit/validate/phone")
async def validate_phone_endpoint(request: Request, body: PhoneValidateBody) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.connectors.common.phone_formatter import (
        format_hk_phone,
        is_mobile,
        is_valid_hk_phone,
    )

    valid = is_valid_hk_phone(body.phone)
    mobile = is_mobile(body.phone) if valid else False
    formatted = ""
    if valid:
        try:
            formatted = format_hk_phone(body.phone)
        except ValueError:
            pass

    return {
        "phone": body.phone,
        "valid": valid,
        "is_mobile": mobile,
        "formatted": formatted,
    }


# ── Generator ──────────────────────────────────────────────────────────────

class GenerateProjectBody(BaseModel):
    project_name: str
    framework: str = "fastapi"
    integrations: list[str] = []
    output_dir: str = ""


@router.post("/api/hk-dev-kit/generate")
async def generate_project(request: Request, body: GenerateProjectBody) -> dict[str, Any]:
    from vibe_coder.hk_dev_kit.generator.scaffolder import ProjectScaffolder

    output_dir = body.output_dir or str(request.app.state.workspace / "generated")
    scaffolder = ProjectScaffolder()
    project_path = scaffolder.generate(
        project_name=body.project_name,
        framework=body.framework,
        integrations=body.integrations,
        output_dir=output_dir,
    )

    with _db(request) as conn:
        import json
        cursor = conn.execute(
            "INSERT INTO projects (project_name, integrations, created_path) VALUES (?,?,?)",
            (body.project_name, json.dumps(body.integrations), str(project_path)),
        )
        project_id = cursor.lastrowid

    emit_event(
        request.app.state.db_paths["mona_events"],
        event_type="action_completed",
        tool_name="hk-dev-kit",
        summary=f"Project '{body.project_name}' scaffolded at {project_path}",
    )

    return {
        "project_id": project_id,
        "project_name": body.project_name,
        "path": str(project_path),
        "framework": body.framework,
        "integrations": body.integrations,
    }


# ── Snippets ───────────────────────────────────────────────────────────────

@router.get("/api/hk-dev-kit/snippets")
async def search_snippets(
    request: Request,
    q: str = "",
    category: str | None = None,
) -> list[dict[str, Any]]:
    from vibe_coder.hk_dev_kit.snippets.snippet_library import SnippetLibrary

    db_path = request.app.state.db_paths["hk_dev_kit"]
    lib = SnippetLibrary()

    if q:
        snippets = lib.search(q, db_path=db_path, category=category)
    else:
        snippets = lib.list_all(db_path=db_path, category=category)

    return [asdict(s) for s in snippets]


# ── Connectors listing ─────────────────────────────────────────────────────

@router.get("/api/hk-dev-kit/connectors")
async def list_connectors(request: Request) -> list[dict[str, Any]]:
    with _db(request) as conn:
        rows = conn.execute("SELECT * FROM api_configs ORDER BY service_name").fetchall()
    return [dict(r) for r in rows]
