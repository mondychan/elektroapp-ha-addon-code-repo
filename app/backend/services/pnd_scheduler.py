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


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _clear_stale_pnd_lock(lock_path: Path):
    if not lock_path.exists():
        return
    try:
        age_seconds = max(0.0, time_module.time() - lock_path.stat().st_mtime)
        
        # If older than an hour, it's definitely stale.
        if age_seconds > PND_LOCK_STALE_SECONDS:
            lock_path.unlink(missing_ok=True)
            logger.warning("Removed stale PND scheduler lock (age): %s", lock_path)
            return

        # Otherwise check if the process is still running.
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = data.get("pid")

            if pid and not _is_pid_alive(pid):
                lock_path.unlink(missing_ok=True)
                logger.warning("Removed stale PND scheduler lock (dead PID %s): %s", pid, lock_path)
        except (json.JSONDecodeError, OSError, ValueError):
            # If the file is corrupted, we don't remove it unless it's old (to avoid race during write).
            pass
            
    except OSError as exc:
        logger.warning("Unable to evaluate stale PND lock %s: %s", lock_path, exc)


def acquire_pnd_process_lock(runtime_state: RuntimeState, storage_dir: Optional[Path]):
    lock_path = get_pnd_lock_path(storage_dir)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create PND lock directory (%s): %s", lock_path.parent, exc)
        return False

    # Attempt cleanup of dead/old locks before trying to acquire.
    _clear_stale_pnd_lock(lock_path)
    
    try:
        # We use os.open with O_EXCL for atomic creation.
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        # If it still exists after _clear_stale_pnd_lock, it means another process just created it
        # or it is indeed alive and active.
        logger.info("PND scheduler lock already held by another process: %s", lock_path)
        return False
    except OSError as exc:
        logger.warning("Cannot create PND scheduler lock %s: %s", lock_path, exc)
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps({
                "pid": os.getpid(), 
                "created_at": datetime.now(timezone.utc).isoformat()
            }))
    except Exception:
        # Cleanup if we failed to write the content.
        lock_path.unlink(missing_ok=True)
        return False

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


def _has_recent_pnd_gaps(pnd_service, *, now: datetime, tzinfo) -> bool:
    find_first_missing_date = getattr(pnd_service, "find_first_missing_date", None)
    if callable(find_first_missing_date):
        return find_first_missing_date(max_lookback_days=31, tzinfo=tzinfo) is not None

    has_day = getattr(pnd_service, "has_day", None)
    if callable(has_day):
        yesterday = (now - timedelta(days=1)).date().isoformat()
        return not has_day(yesterday)

    return True


def schedule_pnd_loop(
    *,
    load_config_fn,
    resolve_config_and_timezone_fn,
    get_pnd_cfg_fn,
    has_pnd_required_cfg_fn,
    pnd_service,
):
    initial_run = True
    while True:
        try:
            cfg = load_config_fn()
            _, tzinfo = resolve_config_and_timezone_fn(cfg=cfg)
            pnd_cfg = get_pnd_cfg_fn(cfg)
            now = datetime.now(tzinfo)
            start_hour = int(pnd_cfg.get("nightly_sync_window_start_hour", 2) or 2)
            end_hour = int(pnd_cfg.get("nightly_sync_window_end_hour", 7) or 7)

            if not pnd_cfg.get("enabled") or not has_pnd_required_cfg_fn(pnd_cfg):
                initial_run = False
                next_run = now + timedelta(minutes=15)
            else:
                if pnd_cfg.get("verify_on_startup", True) and initial_run:
                    try:
                        pnd_service.verify(pnd_cfg)
                    except PNDServiceError as exc:
                        logger.warning("PND startup verify failed: %s", exc.message)
                        pnd_service.record_error(exc, job_type="startup-verify")

                in_window = should_run_pnd_window(now, start_hour=start_hour, end_hour=end_hour)

                # Prefer full gap detection, but keep compatibility with simpler service doubles.
                has_gaps = _has_recent_pnd_gaps(pnd_service, now=now, tzinfo=tzinfo)

                # We run nightly sync if:
                # 1. We are in the nightly window and we have gaps in data.
                # 2. It's our first run after addon start and we have gaps (catch-up).
                should_sync = pnd_cfg.get("nightly_sync_enabled", True) and has_gaps and (in_window or initial_run)
                
                if should_sync:
                    try:
                        pnd_service.run_nightly_sync(pnd_cfg, tzinfo=tzinfo)
                    except PNDServiceError as exc:
                        logger.warning("PND sync failed: %s", exc.message)
                    
                    # After sync attempt, we wait at least an hour if we are in window,
                    # or just move to regular window schedule if we were doing catch-up.
                    if in_window:
                        next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)
                    else:
                        next_run = _next_pnd_window_start(now, start_hour)
                else:
                    next_run = _next_pnd_window_start(now, start_hour)
                
                initial_run = False

            sleep_seconds = max(60, (next_run - datetime.now(tzinfo)).total_seconds())
        except Exception as exc:
            logger.warning("PND scheduler iteration failed, retrying in 10 minutes: %s", exc)
            sleep_seconds = 600
        time_module.sleep(sleep_seconds)
