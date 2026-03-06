"""Unified FastAPI application for the Vibe Coder Dashboard."""

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

from vibe_coder.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("vibe-coder")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = Path(config.database.workspace_path).expanduser()

    logger.info("Vibe Coder Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("Vibe Coder Dashboard shutting down")


app = FastAPI(
    title="Vibe Coder Dashboard",
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
        "active_tab": extra.get("active_tab", "code-qwen"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/code-qwen/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from vibe_coder.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    config.extra["developer_name"] = form.get("developer_name", "")
    langs = form.getlist("preferred_languages")
    if langs:
        config.extra["preferred_languages"] = list(langs)
    config.extra["coding_style"] = form.get("coding_style", "pep8")
    config.extra["default_output_language"] = form.get("default_output_language", "en")

    config.extra["model_mode"] = form.get("model_mode", "warm")
    config.extra["context_window"] = int(form.get("context_window", "32768"))

    config.extra["default_base_branch"] = form.get("default_base_branch", "main")
    config.extra["commit_format"] = form.get("commit_format", "conventional")
    config.extra["github_token_source"] = form.get("github_token_source", "gh_auth")

    config.messaging.telegram_bot_token = form.get("telegram_token", "")

    config.extra["octopus_merchant_id"] = form.get("octopus_merchant_id", "")
    config.extra["fps_proxy_type"] = form.get("fps_proxy_type", "mobile")

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
        "name": "Telegram Bot",
        "ok": bool(config.messaging.telegram_bot_token),
    })

    # Git check
    try:
        import git  # noqa: F401
        results.append({"name": "GitPython", "ok": True})
    except ImportError:
        results.append({"name": "GitPython", "ok": False})

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

from vibe_coder.code_qwen.routes import router as code_qwen_router  # noqa: E402
from vibe_coder.docu_writer.routes import router as docu_writer_router  # noqa: E402
from vibe_coder.git_assistant.routes import router as git_assistant_router  # noqa: E402
from vibe_coder.hk_dev_kit.routes import router as hk_dev_kit_router  # noqa: E402

app.include_router(code_qwen_router)
app.include_router(docu_writer_router)
app.include_router(git_assistant_router)
app.include_router(hk_dev_kit_router)

config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "code_qwen": str(Path(config.database.workspace_path).expanduser() / "code_qwen.db"),
    "docu_writer": str(Path(config.database.workspace_path).expanduser() / "docu_writer.db"),
    "git_assistant": str(Path(config.database.workspace_path).expanduser() / "git_assistant.db"),
    "hk_dev_kit": str(Path(config.database.workspace_path).expanduser() / "hk_dev_kit.db"),
}
app.include_router(create_health_router("vibe-coder", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "vibe-coder",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "vibe_coder.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
