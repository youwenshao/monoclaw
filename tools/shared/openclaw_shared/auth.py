"""PIN-based authentication middleware for local dashboards."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from fastapi import Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware


def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


class PINAuthMiddleware(BaseHTTPMiddleware):
    """Simple PIN authentication for local dashboard access.

    Skips auth for /health, /api/internal, and static files.
    On first access with no PIN configured, redirects to /auth/setup.
    """

    SKIP_PREFIXES = ("/health", "/api/internal", "/static", "/auth", "/favicon.ico")

    def __init__(self, app: Any, config_path: str, session_ttl_hours: int = 24) -> None:
        super().__init__(app)
        self._config_path = config_path
        self._session_ttl = session_ttl_hours * 3600
        self._sessions: dict[str, float] = {}
        self._pin_hash: str = ""

    def _is_authenticated(self, request: Request) -> bool:
        token = request.cookies.get("openclaw_session")
        if not token:
            return False
        expiry = self._sessions.get(token, 0)
        if time.time() > expiry:
            self._sessions.pop(token, None)
            return False
        return True

    def _create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        self._sessions[token] = time.time() + self._session_ttl
        return token

    async def dispatch(self, request: Request, call_next: Any) -> Response:
        path = request.url.path
        if any(path.startswith(p) for p in self.SKIP_PREFIXES):
            return await call_next(request)

        if not self._pin_hash:
            if path != "/auth/setup":
                return RedirectResponse("/auth/setup")
            return await call_next(request)

        if self._is_authenticated(request):
            return await call_next(request)

        if path == "/auth/login" and request.method == "POST":
            return await call_next(request)

        return RedirectResponse("/auth/login")

    def set_pin(self, pin: str) -> None:
        self._pin_hash = _hash_pin(pin)

    def verify_pin(self, pin: str) -> str | None:
        """Return a session token if PIN is correct, else None."""
        if _hash_pin(pin) == self._pin_hash:
            return self._create_session()
        return None


def create_auth_router(middleware: PINAuthMiddleware) -> "APIRouter":
    from fastapi import APIRouter, Form

    router = APIRouter(prefix="/auth")

    @router.get("/setup")
    async def setup_page() -> HTMLResponse:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html><head><title>Set PIN</title>
        <style>body{font-family:Inter,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#1a1f36;color:#fff;margin:0}
        .card{background:#252a40;padding:2rem;border-radius:12px;width:320px}
        input{width:100%;padding:12px;margin:8px 0;border:1px solid #3a3f56;border-radius:8px;background:#1a1f36;color:#fff;font-size:16px;box-sizing:border-box}
        button{width:100%;padding:12px;background:#d4a843;border:none;border-radius:8px;color:#1a1f36;font-weight:600;font-size:16px;cursor:pointer;margin-top:8px}
        h2{margin:0 0 16px;color:#d4a843}</style></head>
        <body><div class="card"><h2>Set Dashboard PIN</h2>
        <form method="post" action="/auth/setup">
        <input type="password" name="pin" placeholder="Enter PIN (4+ digits)" minlength="4" required>
        <input type="password" name="pin_confirm" placeholder="Confirm PIN" minlength="4" required>
        <button type="submit">Set PIN</button></form></div></body></html>
        """)

    @router.post("/setup")
    async def setup_pin(pin: str = Form(...), pin_confirm: str = Form(...)) -> Response:
        if pin != pin_confirm or len(pin) < 4:
            return RedirectResponse("/auth/setup", status_code=303)
        middleware.set_pin(pin)
        token = middleware.verify_pin(pin)
        resp = RedirectResponse("/", status_code=303)
        if token:
            resp.set_cookie("openclaw_session", token, httponly=True, samesite="lax")
        return resp

    @router.get("/login")
    async def login_page() -> HTMLResponse:
        return HTMLResponse("""
        <!DOCTYPE html>
        <html><head><title>Login</title>
        <style>body{font-family:Inter,sans-serif;display:flex;justify-content:center;align-items:center;min-height:100vh;background:#1a1f36;color:#fff;margin:0}
        .card{background:#252a40;padding:2rem;border-radius:12px;width:320px}
        input{width:100%;padding:12px;margin:8px 0;border:1px solid #3a3f56;border-radius:8px;background:#1a1f36;color:#fff;font-size:16px;box-sizing:border-box}
        button{width:100%;padding:12px;background:#d4a843;border:none;border-radius:8px;color:#1a1f36;font-weight:600;font-size:16px;cursor:pointer;margin-top:8px}
        h2{margin:0 0 16px;color:#d4a843}</style></head>
        <body><div class="card"><h2>Dashboard Login</h2>
        <form method="post" action="/auth/login">
        <input type="password" name="pin" placeholder="Enter PIN" required>
        <button type="submit">Login</button></form></div></body></html>
        """)

    @router.post("/login")
    async def login(pin: str = Form(...)) -> Response:
        token = middleware.verify_pin(pin)
        if token:
            resp = RedirectResponse("/", status_code=303)
            resp.set_cookie("openclaw_session", token, httponly=True, samesite="lax")
            return resp
        return RedirectResponse("/auth/login", status_code=303)

    return router
