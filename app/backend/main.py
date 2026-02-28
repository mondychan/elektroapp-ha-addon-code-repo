from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import app_service
from container import build_container
from errors import register_error_handling
from routers.api_router import router as api_router


def _wire_service_from_container():
    container = build_container()
    cfg = container.config
    app_service.CONFIG_FILE = cfg.config_file
    app_service.HA_OPTIONS_FILE = cfg.ha_options_file
    app_service.STORAGE_DIR = cfg.storage_dir
    app_service.CACHE_DIR = cfg.cache_dir
    app_service.CONSUMPTION_CACHE_DIR = cfg.consumption_cache_dir
    app_service.EXPORT_CACHE_DIR = cfg.export_cache_dir
    app_service.OPTIONS_BACKUP_FILE = cfg.options_backup_file
    app_service.FEES_HISTORY_FILE = cfg.fees_history_file
    return container


app = FastAPI(title="Elektroapp API")
app.state.container = _wire_service_from_container()
register_error_handling(app, app_service.logger)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.on_event("startup")
def startup_hook():
    app_service.start_prefetch_scheduler()
    app_service.log_cache_status()


build_path = Path(__file__).parent / "frontend_build"
if build_path.exists():
    app.mount("/static", StaticFiles(directory=build_path / "static"), name="static")

    @app.get("/site.webmanifest")
    def manifest():
        return FileResponse(build_path / "site.webmanifest")

    @app.get("/favicon.ico")
    def favicon():
        return FileResponse(build_path / "favicon.ico")

    @app.get("/android-chrome-192x192.png")
    def favicon192():
        return FileResponse(build_path / "android-chrome-192x192.png")

    @app.get("/android-chrome-512x512.png")
    def favicon512():
        return FileResponse(build_path / "android-chrome-512x512.png")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        return FileResponse(build_path / "index.html")
