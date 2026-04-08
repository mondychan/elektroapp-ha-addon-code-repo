import threading
import os
import json
import logging
import time as time_module
from datetime import datetime, timedelta, timezone, time as datetime_time
from pathlib import Path
from typing import Optional

from services.runtime_state import RuntimeState

logger = logging.getLogger("uvicorn.error")

PREFETCH_LOCK_STALE_SECONDS = 3600

def get_prefetch_lock_path(storage_dir: Optional[Path]):
    if storage_dir:
        return storage_dir / "prefetch-scheduler.lock"
    return Path("/tmp") / "elektroapp-prefetch-scheduler.lock"


def _is_pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True

def _clear_stale_prefetch_lock(lock_path: Path):
    if not lock_path.exists():
        return
    try:
        age_seconds = max(0.0, time_module.time() - lock_path.stat().st_mtime)
        if age_seconds > PREFETCH_LOCK_STALE_SECONDS:
            lock_path.unlink(missing_ok=True)
            logger.warning("Removed stale prefetch scheduler lock (age): %s", lock_path)
            return
            
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = data.get("pid")
            
            # If the PID matches our current PID, but we are just starting (we don't own the lock yet),
            # it means the lock is from a previous run of the same container/process.
            if pid == os.getpid():
                lock_path.unlink(missing_ok=True)
                logger.warning("Removed stale prefetch scheduler lock (reused PID %s): %s", pid, lock_path)
                return

            if pid and not _is_pid_alive(pid):
                lock_path.unlink(missing_ok=True)
                logger.warning("Removed stale prefetch scheduler lock (dead PID %s): %s", pid, lock_path)
        except (json.JSONDecodeError, OSError, ValueError):
            pass
            
    except OSError as exc:
        logger.warning("Unable to evaluate stale prefetch lock %s: %s", lock_path, exc)

def acquire_prefetch_process_lock(runtime_state: RuntimeState, storage_dir: Optional[Path]):
    lock_path = get_prefetch_lock_path(storage_dir)
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create prefetch lock directory (%s): %s", lock_path.parent, exc)
        return False

    _clear_stale_prefetch_lock(lock_path)

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.info("Prefetch scheduler lock already held by another process: %s", lock_path)
        return False
    except OSError as exc:
        logger.warning("Cannot create prefetch scheduler lock %s: %s", lock_path, exc)
        return False

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "pid": os.getpid(),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
    except Exception:
        lock_path.unlink(missing_ok=True)
        return False

    runtime_state.prefetch_lock_owned = True
    runtime_state.prefetch_lock_path = lock_path
    return True

def release_prefetch_process_lock(runtime_state: RuntimeState):
    if not runtime_state.prefetch_lock_owned or not runtime_state.prefetch_lock_path:
        return
    try:
        runtime_state.prefetch_lock_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Unable to remove prefetch scheduler lock %s: %s", runtime_state.prefetch_lock_path, exc)
    finally:
        runtime_state.prefetch_lock_owned = False
        runtime_state.prefetch_lock_path = None

def start_prefetch_scheduler(runtime_state: RuntimeState, storage_dir: Optional[Path], schedule_loop_target):
    with runtime_state.prefetch_thread_guard:
        if runtime_state.prefetch_thread and runtime_state.prefetch_thread.is_alive():
            logger.info("Prefetch scheduler already running in current process.")
            return False

        if not acquire_prefetch_process_lock(runtime_state, storage_dir):
            return False

        runtime_state.prefetch_thread = threading.Thread(
            target=schedule_loop_target,
            daemon=True,
            name="prefetch-scheduler",
        )
        runtime_state.prefetch_thread.start()
        logger.info("Prefetch scheduler started in process %s", os.getpid())
        return True

def schedule_prefetch_loop(
    load_config_fn,
    get_price_provider_fn,
    resolve_config_and_timezone_fn,
    has_price_cache_fn,
    get_prices_for_date_fn,
):
    while True:
        try:
            cfg = load_config_fn()
            provider = get_price_provider_fn(cfg)
            _, tzinfo = resolve_config_and_timezone_fn(cfg=cfg)
            now = datetime.now(tzinfo)
            tomorrow = now.date() + timedelta(days=1)
            tomorrow_str = tomorrow.strftime("%Y-%m-%d")
            target_today = datetime.combine(now.date(), datetime_time(13, 5), tzinfo)
            next_run = None

            if has_price_cache_fn(tomorrow_str, provider=provider):
                logger.info("Tomorrow prices already cached (%s); next check tomorrow.", tomorrow_str)
                next_run = datetime.combine(now.date() + timedelta(days=1), datetime_time(13, 5), tzinfo)
            else:
                if now < target_today:
                    next_run = target_today
                else:
                    try:
                        get_prices_for_date_fn(cfg, tomorrow_str, tzinfo)
                    except Exception as exc:
                        logger.warning("Prefetch failed for %s: %s", tomorrow_str, exc)
                    
                    if has_price_cache_fn(tomorrow_str, provider=provider):
                        next_run = datetime.combine(now.date() + timedelta(days=1), datetime_time(13, 5), tzinfo)
                    else:
                        next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)

            sleep_seconds = max(30, (next_run - datetime.now(tzinfo)).total_seconds())
        except Exception as exc:
            logger.warning("Scheduler iteration failed, retrying in 5 minutes: %s", exc)
            sleep_seconds = 300
        time_module.sleep(sleep_seconds)
