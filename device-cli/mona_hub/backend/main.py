"""Mona Hub — FastAPI application serving the onboarding UI and OpenClaw APIs."""

import json
import threading
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.routers import chat, onboarding, system, voice


FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
ROUTING_CONFIG_PATH = Path("/opt/openclaw/state/routing-config.json")


def _warm_moderate_model():
    """Background: load the moderate route model so first user message is snappy."""
    try:
        from backend.services.llm import llm_service
        llm_service.select_model(model_id=None, complexity="moderate")
    except Exception:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ROUTING_CONFIG_PATH.exists():
        try:
            config = json.loads(ROUTING_CONFIG_PATH.read_text())
            if config.get("auto_routing_enabled") and config.get("routes", {}).get("moderate"):
                t = threading.Thread(target=_warm_moderate_model, daemon=True)
                t.start()
        except (json.JSONDecodeError, OSError):
            pass
    yield


app = FastAPI(title="Mona Hub", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for router in (chat.router, onboarding.router, system.router, voice.router):
    app.include_router(router)

from fastapi.responses import HTMLResponse, FileResponse

@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    # If the path starts with api/, it should have been caught by the routers
    if full_path.startswith("api/"):
        return HTMLResponse("API route not found", status_code=404)
        
    if FRONTEND_DIST.is_dir():
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        
        index_path = FRONTEND_DIST / "index.html"
        if index_path.is_file():
            return FileResponse(index_path)

    # Fallback if frontend is not built
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
        <head>
            <title>Mona Hub</title>
            <style>
                body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; background: #f9fafb; color: #333; }
                .card { text-align: center; padding: 3rem; background: white; border-radius: 16px; box-shadow: 0 10px 25px rgba(0,0,0,0.05); max-width: 500px; }
                h1 { color: #0D9488; margin-top: 0; font-size: 2rem; }
                p { line-height: 1.5; color: #4b5563; }
                .status { display: inline-block; padding: 0.5rem 1rem; background: #ecfdf5; color: #047857; border-radius: 9999px; font-weight: 500; font-size: 0.875rem; margin-top: 1rem; }
                .note { margin-top: 2rem; font-size: 0.875rem; color: #9ca3af; }
            </style>
        </head>
        <body>
            <div class="card">
                <h1>Mona Hub</h1>
                <p>The Mona Hub backend services are running successfully.</p>
                <div class="status">System Ready</div>
                <p class="note">The frontend UI is currently under development and will be deployed in a future update.</p>
            </div>
        </body>
    </html>
    """)
