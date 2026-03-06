"""Unified FastAPI application for the Academic Dashboard."""

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

from academic.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("academic")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = Path(config.database.workspace_path).expanduser()

    logger.info("Academic Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("Academic Dashboard shutting down")


app = FastAPI(
    title="Academic Dashboard",
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
        "active_tab": extra.get("active_tab", "paper-sieve"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/paper-sieve/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from academic.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    config.extra["researcher_name_en"] = form.get("researcher_name_en", "")
    config.extra["researcher_name_tc"] = form.get("researcher_name_tc", "")
    config.extra["institution"] = form.get("institution", "")
    config.extra["department"] = form.get("department", "")
    config.extra["research_areas"] = form.get("research_areas", "")
    config.extra["appointment_date"] = form.get("appointment_date", "")
    config.extra["orcid"] = form.get("orcid", "")
    config.extra["google_scholar_id"] = form.get("google_scholar_id", "")
    config.messaging.twilio_account_sid = form.get("twilio_sid", "")
    config.messaging.twilio_auth_token = form.get("twilio_token", "")
    config.messaging.twilio_whatsapp_from = form.get("whatsapp_from", "")
    config.messaging.telegram_bot_token = form.get("telegram_token", "")
    config.messaging.default_language = form.get("default_language", "en")
    config.extra["default_citation_style"] = form.get("default_citation_style", "apa7")
    config.extra["default_source_language"] = form.get("default_source_language", "tc")
    config.extra["default_target_language"] = form.get("default_target_language", "en")
    config.extra["crossref_email"] = form.get("crossref_email", "")

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
        "name": "CrossRef Email",
        "ok": bool(config.extra.get("crossref_email")),
    })
    results.append({
        "name": "ORCID",
        "ok": bool(config.extra.get("orcid")),
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

from academic.paper_sieve.routes import router as paper_sieve_router  # noqa: E402
from academic.cite_bot.routes import router as cite_bot_router  # noqa: E402
from academic.translate_assist.routes import router as translate_assist_router  # noqa: E402
from academic.grant_tracker.routes import router as grant_tracker_router  # noqa: E402

app.include_router(paper_sieve_router)
app.include_router(cite_bot_router)
app.include_router(translate_assist_router)
app.include_router(grant_tracker_router)

config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "paper_sieve": str(Path(config.database.workspace_path).expanduser() / "paper_sieve.db"),
    "cite_bot": str(Path(config.database.workspace_path).expanduser() / "cite_bot.db"),
    "translate_assist": str(Path(config.database.workspace_path).expanduser() / "translate_assist.db"),
    "grant_tracker": str(Path(config.database.workspace_path).expanduser() / "grant_tracker.db"),
}
app.include_router(create_health_router("academic", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "academic",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "academic.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
