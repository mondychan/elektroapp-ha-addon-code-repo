from pathlib import Path
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

import app_service
import config_loader
from container import build_container
from errors import register_error_handling
from routers.api_router import router as api_router
from static_serving import mount_frontend_static_dirs, spa_index_response


def _wire_service_from_container():
    container = build_container()
    cfg = container.config
    app_service.CONFIG_FILE = cfg.config_file
    app_service.HA_OPTIONS_FILE = cfg.ha_options_file
    app_service.STORAGE_DIR = cfg.storage_dir
    app_service.CACHE_DIR = cfg.cache_dir
    app_service.CONSUMPTION_CACHE_DIR = cfg.consumption_cache_dir
    app_service.EXPORT_CACHE_DIR = cfg.export_cache_dir
    app_service.PND_CACHE_DIR = cfg.pnd_cache_dir
    app_service.OPTIONS_BACKUP_FILE = cfg.options_backup_file
    app_service.FEES_HISTORY_FILE = cfg.fees_history_file
    config_loader.CONFIG_FILE = cfg.config_file
    config_loader.HA_OPTIONS_FILE = cfg.ha_options_file
    config_loader.STORAGE_DIR = cfg.storage_dir
    config_loader.OPTIONS_BACKUP_FILE = cfg.options_backup_file
    config_loader.FEES_HISTORY_FILE = cfg.fees_history_file
    app_service.finalize_initialization()
    return container


app = FastAPI(title="Elektroapp API")
app.state.container = _wire_service_from_container()
register_error_handling(app, app_service.logger)

if app.state.container.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=app.state.container.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.middleware("http")
async def access_log_middleware(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    app_service.logger.info(
        "request method=%s path=%s status=%s duration_ms=%s request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        getattr(request.state, "request_id", None),
    )
    response.headers["X-Response-Time-Ms"] = str(elapsed_ms)
    return response

app.include_router(api_router)


@app.on_event("startup")
def startup_hook():
    app_service.start_prefetch_scheduler()
    app_service.start_pnd_scheduler()
    app_service.log_cache_status()


@app.get("/health")
def health():
    return {
        "status": "ok",
        "version": app_service.APP_VERSION,
        "api_token_configured": app.state.container.api_token_configured,
    }


build_path = Path(__file__).parent / "frontend_build"


if build_path.exists():
    mount_frontend_static_dirs(app, build_path)

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

    @app.get("/")
    def serve_react_root():
        return spa_index_response(build_path / "index.html")

    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        return spa_index_response(build_path / "index.html")
