import os
import time
from datetime import datetime

import pytest


def test_start_prefetch_scheduler_starts_only_once_per_process(monkeypatch, backend_main, isolated_storage):
    starts = []

    class FakeThread:
        def __init__(self, target=None, daemon=None, name=None):
            self.target = target
            self.daemon = daemon
            self.name = name
            self._alive = False

        def start(self):
            self._alive = True
            starts.append(self.name)

        def is_alive(self):
            return self._alive

    monkeypatch.setattr(backend_main.threading, "Thread", FakeThread)
    monkeypatch.setattr(backend_main, "acquire_prefetch_process_lock", lambda: True)
    backend_main.RUNTIME_STATE.prefetch_thread = None

    started_first = backend_main.start_prefetch_scheduler()
    started_second = backend_main.start_prefetch_scheduler()

    assert started_first is True
    assert started_second is False
    assert starts == ["prefetch-scheduler"]


def test_start_pnd_scheduler_starts_only_once_per_process(monkeypatch, backend_main, isolated_storage):
    calls = []

    monkeypatch.setattr(
        backend_main,
        "start_pnd_scheduler_fn",
        lambda runtime_state, storage_dir, schedule_loop_target: calls.append("pnd-scheduler") is None and len(calls) == 1,
    )
    monkeypatch.setattr(backend_main, "PND_SERVICE", object())

    started_first = backend_main.start_pnd_scheduler()
    started_second = backend_main.start_pnd_scheduler()

    assert started_first is True
    assert started_second is False
    assert calls == ["pnd-scheduler", "pnd-scheduler"]


def test_acquire_prefetch_process_lock_is_exclusive(backend_main, isolated_storage):
    lock_path = backend_main.get_prefetch_lock_path()
    lock_path.unlink(missing_ok=True)

    backend_main.RUNTIME_STATE.prefetch_lock_owned = False
    backend_main.RUNTIME_STATE.prefetch_lock_path = None

    first = backend_main.acquire_prefetch_process_lock()
    assert first is True
    assert lock_path.exists() is True

    # Simulate a second process trying to acquire the same file lock.
    backend_main.RUNTIME_STATE.prefetch_lock_owned = False
    backend_main.RUNTIME_STATE.prefetch_lock_path = None
    second = backend_main.acquire_prefetch_process_lock()
    assert second is False

    lock_path.unlink(missing_ok=True)


def test_acquire_prefetch_process_lock_removes_stale_lock(backend_main, isolated_storage):
    lock_path = backend_main.get_prefetch_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("stale", encoding="utf-8")
    stale_mtime = time.time() - (backend_main.PREFETCH_LOCK_STALE_SECONDS + 10)
    os.utime(lock_path, (stale_mtime, stale_mtime))

    backend_main.RUNTIME_STATE.prefetch_lock_owned = False
    backend_main.RUNTIME_STATE.prefetch_lock_path = None

    acquired = backend_main.acquire_prefetch_process_lock()
    assert acquired is True
    assert lock_path.exists() is True

    backend_main.release_prefetch_process_lock()


def test_schedule_pnd_loop_retries_until_success_then_stops_after_cache(monkeypatch):
    from services import pnd_scheduler
    from services.pnd_service import PNDServiceError

    now_values = iter(
        [
            datetime(2026, 4, 5, 2, 10, 0),
            datetime(2026, 4, 5, 2, 10, 0),
            datetime(2026, 4, 5, 3, 10, 0),
            datetime(2026, 4, 5, 3, 10, 0),
            datetime(2026, 4, 5, 4, 10, 0),
            datetime(2026, 4, 5, 4, 10, 0),
        ]
    )

    class FakeDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = next(now_values)
            return value.replace(tzinfo=tz)

    class FakeService:
        def __init__(self):
            self.verify_calls = 0
            self.sync_calls = 0
            self.recorded_errors = []
            self.cached = False

        def verify(self, pnd_cfg):
            self.verify_calls += 1
            return {"ok": True}

        def has_day(self, date_str):
            return self.cached

        def run_nightly_sync(self, pnd_cfg, tzinfo=None):
            self.sync_calls += 1
            if self.sync_calls == 1:
                raise PNDServiceError("PND_DATA_NOT_AVAILABLE", "not ready", stage="nightly", status_code=409)
            self.cached = True
            return {"ok": True}

        def record_error(self, exc, job_type, extra=None):
            self.recorded_errors.append((exc.code, job_type, extra))

    fake_service = FakeService()
    sleep_calls = []

    def fake_sleep(seconds):
        sleep_calls.append(seconds)
        if len(sleep_calls) >= 3:
            raise RuntimeError("stop-loop")

    monkeypatch.setattr(pnd_scheduler, "datetime", FakeDateTime)
    monkeypatch.setattr(pnd_scheduler.time_module, "sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="stop-loop"):
        pnd_scheduler.schedule_pnd_loop(
            load_config_fn=lambda: {
                "pnd": {
                    "enabled": True,
                    "username": "user",
                    "password": "pass",
                    "meter_id": "3000012345",
                    "verify_on_startup": True,
                    "nightly_sync_enabled": True,
                    "nightly_sync_window_start_hour": 2,
                    "nightly_sync_window_end_hour": 7,
                }
            },
            resolve_config_and_timezone_fn=lambda cfg=None: (cfg, None),
            get_pnd_cfg_fn=lambda cfg: cfg["pnd"],
            has_pnd_required_cfg_fn=lambda pnd_cfg: True,
            pnd_service=fake_service,
        )

    assert fake_service.verify_calls == 1
    assert fake_service.sync_calls == 2
    assert fake_service.cached is True
    assert sleep_calls[0] > 0
    assert sleep_calls[-1] > 60 * 60 * 12
