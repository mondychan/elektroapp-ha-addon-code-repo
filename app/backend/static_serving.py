from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


def spa_index_response(path: Path) -> FileResponse:
    return FileResponse(
        path,
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


def mount_frontend_static_dirs(app: FastAPI, build_path: Path) -> None:
    """Mount known frontend asset directories when they exist.

    CRA emits `static/`; Vite emits `assets/`. Mounting conditionally keeps the
    backend importable across both build layouts.
    """
    for route_path, dirname in (("/static", "static"), ("/assets", "assets")):
        asset_dir = build_path / dirname
        if asset_dir.exists():
            app.mount(route_path, StaticFiles(directory=asset_dir), name=dirname)
