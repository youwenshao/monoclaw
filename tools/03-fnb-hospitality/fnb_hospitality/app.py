"""Unified FastAPI application for the F&B Hospitality Dashboard."""

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

from fnb_hospitality.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("fnb-hospitality")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = Path(config.database.workspace_path).expanduser()

    logger.info("F&B Hospitality Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("F&B Hospitality Dashboard shutting down")


app = FastAPI(
    title="F&B Hospitality Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

_auth_middleware = PINAuthMiddleware(app, config_path=str(CONFIG_PATH))
app.add_middleware(PINAuthMiddleware, config_path=str(CONFIG_PATH))
auth_router = create_auth_router(_auth_middleware)
app.include_router(auth_router)


# -- Shared API routes -----------------------------------------------------

@app.get("/api/events")
async def api_events(request: Request, limit: int = 50) -> list[dict]:
    db_paths = request.app.state.db_paths
    return get_events(db_paths["mona_events"], limit=limit)


@app.get("/api/events/{event_id}/acknowledge", status_code=204)
async def acknowledge_event(request: Request, event_id: int) -> None:
    from openclaw_shared.mona_events import acknowledge_event as ack
    ack(request.app.state.db_paths["mona_events"], event_id)


# -- Dashboard pages -------------------------------------------------------

def _ctx(request: Request, **extra: object) -> dict:
    """Build common template context."""
    return {
        "request": request,
        "config": request.app.state.config,
        "active_tab": extra.get("active_tab", "table-master"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/table-master/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from fnb_hospitality.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    config.extra["restaurant_name"] = form.get("restaurant_name", "")
    config.extra["restaurant_address"] = form.get("restaurant_address", "")
    config.extra["cuisine_type"] = form.get("cuisine_type", "")
    config.extra["phone"] = form.get("phone", "")
    config.messaging.twilio_account_sid = form.get("twilio_sid", "")
    config.messaging.twilio_auth_token = form.get("twilio_token", "")
    config.messaging.twilio_whatsapp_from = form.get("whatsapp_from", "")
    config.messaging.telegram_bot_token = form.get("telegram_token", "")
    config.messaging.default_language = form.get("default_language", "zh")
    config.extra["openrice_api_key"] = form.get("openrice_api_key", "")
    config.extra["instagram_access_token"] = form.get("instagram_access_token", "")

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
    results.append({
        "name": "OpenRice API",
        "ok": bool(config.extra.get("openrice_api_key")),
    })
    results.append({
        "name": "Instagram Graph API",
        "ok": bool(config.extra.get("instagram_access_token")),
    })

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


# -- Import and mount tool routers -----------------------------------------

from fnb_hospitality.table_master.routes import router as table_master_router  # noqa: E402
from fnb_hospitality.queue_bot.routes import router as queue_bot_router  # noqa: E402
from fnb_hospitality.no_show_shield.routes import router as no_show_shield_router  # noqa: E402
from fnb_hospitality.sommelier_memory.routes import router as sommelier_memory_router  # noqa: E402

app.include_router(table_master_router)
app.include_router(queue_bot_router)
app.include_router(no_show_shield_router)
app.include_router(sommelier_memory_router)

config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "table_master": str(Path(config.database.workspace_path).expanduser() / "table_master.db"),
    "queue_bot": str(Path(config.database.workspace_path).expanduser() / "queue_bot.db"),
    "no_show_shield": str(Path(config.database.workspace_path).expanduser() / "no_show_shield.db"),
    "sommelier_memory": str(Path(config.database.workspace_path).expanduser() / "sommelier_memory.db"),
}
app.include_router(create_health_router("fnb-hospitality", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "fnb-hospitality",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "fnb_hospitality.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
