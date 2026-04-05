import json
import logging
import os
import threading
import time as time_module
from datetime import datetime, timedelta, timezone, time as datetime_time
from pathlib import Path
from typing import Optional

from services.pnd_service import PNDServiceError, should_run_pnd_window
from services.runtime_state import RuntimeState


logger = logging.getLogger("uvicorn.error")
PND_LOCK_STALE_SECONDS = 3600


def get_pnd_lock_path(storage_dir: Optional[Path]):
    if storage_dir:
        return storage_dir / "pnd-scheduler.lock"
    return Path("/tmp") / "elektroapp-pnd-scheduler.lock"


def _clear_stale_pnd_lock(lock_path: Path):
    if not lock_path.exists():
        return
    try:
        age_seconds = max(0.0, time_module.time() - lock_path.stat().st_mtime)
        if age_seconds > PND_LOCK_STALE_SECONDS:
            lock_path.unlink(missing_ok=True)
            logger.warning("Removed stale PND scheduler lock: %s", lock_path)
    except OSError as exc:
        logger.warning("Unable to evaluate stale PND lock %s: %s", lock_path, exc)


def acquire_pnd_process_lock(runtime_state: RuntimeState, storage_dir: Optional[Path]):
    lock_path = get_pnd_lock_path(storage_dir)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create PND lock directory (%s): %s", lock_path.parent, exc)
        return False

    _clear_stale_pnd_lock(lock_path)
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.info("PND scheduler lock already held by another process: %s", lock_path)
        return False
    except OSError as exc:
        logger.warning("Cannot create PND scheduler lock %s: %s", lock_path, exc)
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"pid": os.getpid(), "created_at": datetime.now(timezone.utc).isoformat()}))

    runtime_state.pnd_lock_owned = True
    runtime_state.pnd_lock_path = lock_path
    return True


def release_pnd_process_lock(runtime_state: RuntimeState):
    if not runtime_state.pnd_lock_owned or not runtime_state.pnd_lock_path:
        return
    try:
        runtime_state.pnd_lock_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Unable to remove PND scheduler lock %s: %s", runtime_state.pnd_lock_path, exc)
    finally:
        runtime_state.pnd_lock_owned = False
        runtime_state.pnd_lock_path = None


def start_pnd_scheduler(runtime_state: RuntimeState, storage_dir: Optional[Path], schedule_loop_target):
    with runtime_state.pnd_thread_guard:
        if runtime_state.pnd_thread and runtime_state.pnd_thread.is_alive():
            logger.info("PND scheduler already running in current process.")
            return False
        if not acquire_pnd_process_lock(runtime_state, storage_dir):
            return False
        runtime_state.pnd_thread = threading.Thread(
            target=schedule_loop_target,
            daemon=True,
            name="pnd-scheduler",
        )
        runtime_state.pnd_thread.start()
        logger.info("PND scheduler started in process %s", os.getpid())
        return True


def _next_pnd_window_start(now: datetime, start_hour: int) -> datetime:
    candidate = datetime.combine(now.date(), datetime_time(start_hour, 5), now.tzinfo)
    if candidate <= now:
        candidate = datetime.combine(now.date() + timedelta(days=1), datetime_time(start_hour, 5), now.tzinfo)
    return candidate


def schedule_pnd_loop(
    *,
    load_config_fn,
    resolve_config_and_timezone_fn,
    get_pnd_cfg_fn,
    has_pnd_required_cfg_fn,
    pnd_service,
):
    startup_verify_attempted = False
    while True:
        try:
            cfg = load_config_fn()
            _, tzinfo = resolve_config_and_timezone_fn(cfg=cfg)
            pnd_cfg = get_pnd_cfg_fn(cfg)
            now = datetime.now(tzinfo)
            start_hour = int(pnd_cfg.get("nightly_sync_window_start_hour", 2) or 2)
            end_hour = int(pnd_cfg.get("nightly_sync_window_end_hour", 7) or 7)

            if not pnd_cfg.get("enabled") or not has_pnd_required_cfg_fn(pnd_cfg):
                startup_verify_attempted = False
                next_run = now + timedelta(minutes=15)
            else:
                if pnd_cfg.get("verify_on_startup", True) and not startup_verify_attempted:
                    try:
                        pnd_service.verify(pnd_cfg)
                    except PNDServiceError as exc:
                        logger.warning("PND startup verify failed: %s", exc.message)
                        pnd_service.record_error(exc, job_type="startup-verify")
                    startup_verify_attempted = True

                yesterday = (now - timedelta(days=1)).date().isoformat()
                if pnd_cfg.get("nightly_sync_enabled", True) and should_run_pnd_window(now, start_hour=start_hour, end_hour=end_hour) and not pnd_service.has_day(yesterday):
                    try:
                        pnd_service.run_nightly_sync(pnd_cfg, tzinfo=tzinfo)
                    except PNDServiceError as exc:
                        logger.warning("PND nightly sync failed: %s", exc.message)
                    next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)
                else:
                    next_run = _next_pnd_window_start(now, start_hour)

            sleep_seconds = max(30, (next_run - datetime.now(tzinfo)).total_seconds())
        except Exception as exc:
            logger.warning("PND scheduler iteration failed, retrying in 10 minutes: %s", exc)
            sleep_seconds = 600
        time_module.sleep(sleep_seconds)
