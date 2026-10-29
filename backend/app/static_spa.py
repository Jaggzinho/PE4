from __future__ import annotations

import os
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def default_static_dir() -> Path:
    """Return the bundled/repository production frontend directory."""
    frozen_root = getattr(sys, "_MEIPASS", None)
    if frozen_root:
        return Path(frozen_root) / "dist"
    return Path(__file__).resolve().parents[2] / "dist"


def maybe_mount_spa(app: FastAPI) -> None:
    """Mount a configured local Vite build without masking unknown API paths."""
    raw = (os.getenv("PE3_STATIC_DIR") or "").strip()
    static_dir = Path(raw) if raw else default_static_dir()
    index = static_dir / "index.html"
    if not static_dir.exists() or not index.exists():
        return

    assets_dir = static_dir / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    @app.get("/", include_in_schema=False)
    def spa_index():
        return FileResponse(str(index))

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")

        requested = (static_dir / full_path).resolve()
        try:
            requested.relative_to(static_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if requested.is_file():
            return FileResponse(str(requested))
        return FileResponse(str(index))


__all__ = ["default_static_dir", "maybe_mount_spa"]
