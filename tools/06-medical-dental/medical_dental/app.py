"""Unified FastAPI application for the Medical-Dental Dashboard."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from openclaw_shared.auth import PINAuthMiddleware, create_auth_router
from openclaw_shared.config import load_config
from openclaw_shared.export import create_export_router
from openclaw_shared.health import create_health_router
from openclaw_shared.llm import create_llm_provider
from openclaw_shared.logging import setup_logging
from openclaw_shared.mona_events import get_events

from medical_dental.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("medical-dental")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = Path(config.database.workspace_path).expanduser()

    logger.info("Medical-Dental Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("Medical-Dental Dashboard shutting down")


app = FastAPI(
    title="Medical-Dental Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

# Static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Templates
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# Auth middleware
_auth_middleware = PINAuthMiddleware(app, config_path=str(CONFIG_PATH))
app.add_middleware(PINAuthMiddleware, config_path=str(CONFIG_PATH))
auth_router = create_auth_router(_auth_middleware)
app.include_router(auth_router)


# ── Shared API routes ─────────────────────────────────────────────────────

@app.get("/api/events")
async def api_events(request: Request, limit: int = 50) -> list[dict]:
    db_paths = request.app.state.db_paths
    return get_events(db_paths["mona_events"], limit=limit)


@app.get("/api/events/{event_id}/acknowledge", status_code=204)
async def acknowledge_event(request: Request, event_id: int) -> None:
    from openclaw_shared.mona_events import acknowledge_event as ack
    ack(request.app.state.db_paths["mona_events"], event_id)


# ── Dashboard pages ───────────────────────────────────────────────────────

def _ctx(request: Request, **extra: object) -> dict:
    """Build common template context."""
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": extra.get("active_tab", "insurance-agent"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/insurance-agent/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from medical_dental.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    # Clinic profile
    config.extra["clinic_name"] = form.get("clinic_name", "")
    config.extra["hkma_registration"] = form.get("hkma_registration", "")
    config.extra["clinic_address"] = form.get("clinic_address", "")
    config.extra["clinic_phone"] = form.get("clinic_phone", "")

    # Operating hours
    config.extra["morning_start"] = form.get("morning_start", "09:00")
    config.extra["morning_end"] = form.get("morning_end", "13:00")
    config.extra["afternoon_start"] = form.get("afternoon_start", "14:30")
    config.extra["afternoon_end"] = form.get("afternoon_end", "18:00")
    config.extra["saturday_start"] = form.get("saturday_start", "09:00")
    config.extra["saturday_end"] = form.get("saturday_end", "13:00")
    config.extra["evening_enabled"] = bool(form.get("evening_enabled"))

    # Messaging
    config.messaging.twilio_account_sid = form.get("twilio_sid", "")
    config.messaging.twilio_auth_token = form.get("twilio_token", "")
    config.messaging.twilio_whatsapp_from = form.get("whatsapp_from", "")
    config.messaging.telegram_bot_token = form.get("telegram_token", "")
    config.messaging.default_language = form.get("default_language", "en")

    # ScribeAI
    config.extra["whisper_model"] = form.get("whisper_model", "small")

    # MedReminder
    if form.get("compliance_window"):
        config.extra["compliance_window_hours"] = int(form.get("compliance_window", "2"))

    save_config(config, CONFIG_PATH)

    if form.get("seed_demo"):
        seed_all(request.app.state.db_paths)
        logger.info("Demo data seeded via setup wizard")

    return RedirectResponse("/", status_code=303)


@app.get("/api/connection-test")
async def connection_test(request: Request) -> HTMLResponse:
    """Test all configured external connections."""
    config = request.app.state.config
    results = []

    for name, path in request.app.state.db_paths.items():
        exists = Path(path).exists()
        results.append({"name": f"Database: {name}", "ok": exists})

    try:
        llm_health = await request.app.state.llm.health()
        results.append({"name": "LLM Provider", "ok": llm_health.get("status") != "error"})
    except Exception:
        results.append({"name": "LLM Provider", "ok": False})

    results.append({
        "name": "WhatsApp (Twilio)",
        "ok": bool(config.messaging.twilio_account_sid),
    })
    results.append({
        "name": "Telegram Bot",
        "ok": bool(config.messaging.telegram_bot_token),
    })

    # Whisper STT check
    try:
        import mlx_whisper  # noqa: F401
        results.append({"name": "STT: MLX-Whisper", "ok": True})
    except ImportError:
        results.append({"name": "STT: MLX-Whisper", "ok": False})

    # Tesseract OCR check
    try:
        import pytesseract  # noqa: F401
        results.append({"name": "OCR: Tesseract", "ok": True})
    except ImportError:
        results.append({"name": "OCR: Tesseract", "ok": False})

    html_parts = []
    for r in results:
        icon = "green" if r["ok"] else "red"
        label = r["name"]
        status = "Connected" if r["ok"] else "Not configured"
        html_parts.append(
            f'<div class="flex items-center gap-3 p-3 bg-navy-800 rounded-lg">'
            f'<span class="status-dot {icon}"></span>'
            f'<span class="text-sm">{label}</span>'
            f'<span class="ml-auto text-xs text-gray-400">{status}</span>'
            f'</div>'
        )

    return HTMLResponse("\n".join(html_parts))


# ── Import and mount tool routers ─────────────────────────────────────────

from medical_dental.insurance_agent.routes import router as insurance_agent_router  # noqa: E402
from medical_dental.scribe_ai.routes import router as scribe_ai_router  # noqa: E402
from medical_dental.clinic_scheduler.routes import router as clinic_scheduler_router  # noqa: E402
from medical_dental.med_reminder.routes import router as med_reminder_router  # noqa: E402

app.include_router(insurance_agent_router)
app.include_router(scribe_ai_router)
app.include_router(clinic_scheduler_router)
app.include_router(med_reminder_router)

# Health and export
config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "insurance_agent": str(Path(config.database.workspace_path).expanduser() / "insurance_agent.db"),
    "scribe_ai": str(Path(config.database.workspace_path).expanduser() / "scribe_ai.db"),
    "clinic_scheduler": str(Path(config.database.workspace_path).expanduser() / "clinic_scheduler.db"),
    "med_reminder": str(Path(config.database.workspace_path).expanduser() / "med_reminder.db"),
}
app.include_router(create_health_router("medical-dental", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "medical-dental",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "medical_dental.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
