"""Health check endpoint factory for FastAPI tools."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter


_start_time: float = time.time()


def create_health_router(
    tool_name: str,
    version: str,
    db_paths: dict[str, str | Path] | None = None,
) -> APIRouter:
    """Return a FastAPI router with a GET /health endpoint."""
    router = APIRouter()

    @router.get("/health")
    async def health_check() -> dict[str, Any]:
        process = psutil.Process()
        memory_mb = process.memory_info().rss / (1024 * 1024)

        db_status: dict[str, str] = {}
        for name, path in (db_paths or {}).items():
            db_status[name] = "ok" if Path(path).exists() else "missing"

        return {
            "tool": tool_name,
            "version": version,
            "status": "healthy",
            "uptime_seconds": int(time.time() - _start_time),
            "databases": db_status,
            "memory_mb": round(memory_mb, 1),
        }

    return router
