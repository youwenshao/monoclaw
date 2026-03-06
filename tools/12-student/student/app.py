"""Unified FastAPI application for the Student Dashboard."""

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

from student.database import init_all_databases

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR.parent / "config.yaml"
TEMPLATE_DIR = BASE_DIR / "dashboard" / "templates"
STATIC_DIR = BASE_DIR / "dashboard" / "static"

logger = setup_logging("student")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    config = load_config(CONFIG_PATH)
    db_paths = init_all_databases(config.database.workspace_path)
    llm = create_llm_provider(config.llm.provider, model_path=config.llm.model_path)

    workspace = Path(config.database.workspace_path).expanduser()
    chroma_dir = workspace / "chroma_db"
    chroma_dir.mkdir(parents=True, exist_ok=True)

    app.state.config = config
    app.state.db_paths = db_paths
    app.state.llm = llm
    app.state.workspace = workspace
    app.state.chroma_dir = chroma_dir

    logger.info("Student Dashboard starting on port %d", config.port)
    logger.info("Databases initialized: %s", list(db_paths.keys()))
    yield
    logger.info("Student Dashboard shutting down")


app = FastAPI(
    title="Student Dashboard",
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
        "active_tab": extra.get("active_tab", "study-buddy"),
        **extra,
    }


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return RedirectResponse("/study-buddy/")  # type: ignore[return-value]


@app.get("/setup/", response_class=HTMLResponse)
async def setup_wizard(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("setup.html", _ctx(request, active_tab="setup"))


@app.post("/setup/")
async def save_setup(request: Request) -> RedirectResponse:
    """Process the first-run configuration wizard."""
    from openclaw_shared.config import save_config
    from student.seed_data import seed_all

    form = await request.form()
    config = request.app.state.config

    config.extra["student_name"] = form.get("student_name", "")
    config.extra["university"] = form.get("university", "")
    config.extra["programme"] = form.get("programme", "")
    config.extra["year_of_study"] = form.get("year_of_study", "")
    config.extra["expected_graduation"] = form.get("expected_graduation", "")

    config.messaging.twilio_account_sid = form.get("twilio_sid", "")
    config.messaging.twilio_auth_token = form.get("twilio_token", "")
    config.messaging.twilio_whatsapp_from = form.get("whatsapp_from", "")
    config.messaging.telegram_bot_token = form.get("telegram_token", "")
    config.messaging.default_language = form.get("default_language", "en")

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

    chroma_ok = request.app.state.chroma_dir.exists()
    results.append({"name": "ChromaDB", "ok": chroma_ok})

    results.append({
        "name": "WhatsApp (Twilio)",
        "ok": bool(config.messaging.twilio_account_sid),
    })
    results.append({
        "name": "Telegram Bot",
        "ok": bool(config.messaging.telegram_bot_token),
    })

    try:
        from playwright.async_api import async_playwright
        results.append({"name": "Playwright (JobTracker)", "ok": True})
    except ImportError:
        results.append({"name": "Playwright (JobTracker)", "ok": False})

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

from student.study_buddy.routes import router as study_buddy_router  # noqa: E402
from student.exam_generator.routes import router as exam_generator_router  # noqa: E402
from student.thesis_formatter.routes import router as thesis_formatter_router  # noqa: E402
from student.interview_prep.routes import router as interview_prep_router  # noqa: E402
from student.job_tracker.routes import router as job_tracker_router  # noqa: E402

app.include_router(study_buddy_router)
app.include_router(exam_generator_router)
app.include_router(thesis_formatter_router)
app.include_router(interview_prep_router)
app.include_router(job_tracker_router)

config = load_config(CONFIG_PATH)
_db_paths_for_health = {
    "study_buddy": str(Path(config.database.workspace_path).expanduser() / "study_buddy.db"),
    "exam_generator": str(Path(config.database.workspace_path).expanduser() / "exam_generator.db"),
    "thesis_formatter": str(Path(config.database.workspace_path).expanduser() / "thesis_formatter.db"),
    "interview_prep": str(Path(config.database.workspace_path).expanduser() / "interview_prep.db"),
    "job_tracker": str(Path(config.database.workspace_path).expanduser() / "job_tracker.db"),
}
app.include_router(create_health_router("student", "1.0.0", _db_paths_for_health))
app.include_router(
    create_export_router(
        "student",
        _db_paths_for_health,
        str(Path(config.database.workspace_path).expanduser()),
    )
)


def main() -> None:
    import uvicorn
    cfg = load_config(CONFIG_PATH)
    uvicorn.run(
        "student.app:app",
        host="0.0.0.0",
        port=cfg.port,
        reload=True,
        reload_dirs=[str(BASE_DIR)],
    )


if __name__ == "__main__":
    main()
