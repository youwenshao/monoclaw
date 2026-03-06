"""Unified FastAPI application for the Import/Export Dashboard."""

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

from import_export.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("import-export")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = Path(config.database.workspace_path).expanduser()

    logger.info("Import/Export Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("Import/Export Dashboard shutting down")


app = FastAPI(
    title="Import/Export Dashboard",
    version="1.0.0",
    lifespan=lifespan,
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

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
        "active_tab": extra.get("active_tab", "trade-doc-ai"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/trade-doc-ai/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from import_export.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    config.extra["company_name"] = form.get("company_name", "")
    config.extra["br_number"] = form.get("br_number", "")
    config.extra["base_currency"] = form.get("base_currency", "HKD")
    config.extra["principal_business"] = form.get("principal_business", "import-export")

    config.extra["tradelink_username"] = form.get("tradelink_username", "")
    config.extra["tradelink_password"] = form.get("tradelink_password", "")
    config.extra["filing_provider"] = form.get("filing_provider", "tradelink")

    config.messaging.twilio_account_sid = form.get("twilio_sid", "")
    config.messaging.twilio_auth_token = form.get("twilio_token", "")
    config.messaging.twilio_whatsapp_from = form.get("whatsapp_from", "")
    config.messaging.telegram_bot_token = form.get("telegram_token", "")
    config.messaging.default_language = form.get("default_language", "en")

    config.extra["wechat_app_id"] = form.get("wechat_app_id", "")
    config.extra["wechat_app_secret"] = form.get("wechat_app_secret", "")

    if form.get("monitored_currencies"):
        config.extra["monitored_currencies"] = [
            c.strip() for c in form.get("monitored_currencies", "").split(",") if c.strip()
        ]

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
        "name": "WeChat API",
        "ok": bool(config.extra.get("wechat_app_id")),
    })
    results.append({
        "name": "Tradelink Filing",
        "ok": bool(config.extra.get("tradelink_username")),
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


# ── Import and mount tool routers ─────────────────────────────────────────

from import_export.trade_doc_ai.routes import router as trade_doc_ai_router  # noqa: E402
from import_export.supplier_bot.routes import router as supplier_bot_router  # noqa: E402
from import_export.fx_invoice.routes import router as fx_invoice_router  # noqa: E402
from import_export.stock_reconcile.routes import router as stock_reconcile_router  # noqa: E402

app.include_router(trade_doc_ai_router)
app.include_router(supplier_bot_router)
app.include_router(fx_invoice_router)
app.include_router(stock_reconcile_router)

config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "trade_doc_ai": str(Path(config.database.workspace_path).expanduser() / "trade_doc_ai.db"),
    "supplier_bot": str(Path(config.database.workspace_path).expanduser() / "supplier_bot.db"),
    "fx_invoice": str(Path(config.database.workspace_path).expanduser() / "fx_invoice.db"),
    "stock_reconcile": str(Path(config.database.workspace_path).expanduser() / "stock_reconcile.db"),
}
app.include_router(create_health_router("import-export", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "import-export",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "import_export.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
