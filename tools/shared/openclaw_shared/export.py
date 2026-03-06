"""Data export handler — bundles SQLite DBs and workspace files into a ZIP."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse


def create_export_router(
    tool_name: str,
    db_paths: dict[str, str | Path],
    workspace_path: str | Path,
) -> APIRouter:
    """Return a FastAPI router with POST /api/export."""
    router = APIRouter()

    @router.post("/api/export")
    async def export_data() -> FileResponse:
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"openclaw-export-{tool_name}-"))
        export_dir = tmp_dir / tool_name

        # Copy databases
        db_dir = export_dir / "databases"
        db_dir.mkdir(parents=True)
        for name, path in db_paths.items():
            src = Path(path)
            if src.exists():
                shutil.copy2(src, db_dir / f"{name}.db")

        # Copy workspace files
        ws = Path(workspace_path).expanduser()
        if ws.exists():
            shutil.copytree(ws, export_dir / "workspace", dirs_exist_ok=True)

        archive_path = shutil.make_archive(
            str(tmp_dir / f"{tool_name}-export"), "zip", str(export_dir)
        )
        return FileResponse(
            archive_path,
            media_type="application/zip",
            filename=f"{tool_name}-export.zip",
        )

    return router
