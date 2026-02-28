import os
import time


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
    monkeypatch.setattr(backend_main, "_PREFETCH_THREAD", None)

    started_first = backend_main.start_prefetch_scheduler()
    started_second = backend_main.start_prefetch_scheduler()

    assert started_first is True
    assert started_second is False
    assert starts == ["prefetch-scheduler"]


def test_acquire_prefetch_process_lock_is_exclusive(backend_main, isolated_storage):
    lock_path = backend_main.get_prefetch_lock_path()
    lock_path.unlink(missing_ok=True)

    backend_main._PREFETCH_LOCK_OWNED = False
    backend_main._PREFETCH_LOCK_PATH = None

    first = backend_main.acquire_prefetch_process_lock()
    assert first is True
    assert lock_path.exists() is True

    # Simulate a second process trying to acquire the same file lock.
    backend_main._PREFETCH_LOCK_OWNED = False
    backend_main._PREFETCH_LOCK_PATH = None
    second = backend_main.acquire_prefetch_process_lock()
    assert second is False

    lock_path.unlink(missing_ok=True)


def test_acquire_prefetch_process_lock_removes_stale_lock(backend_main, isolated_storage):
    lock_path = backend_main.get_prefetch_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text("stale", encoding="utf-8")
    stale_mtime = time.time() - (backend_main.PREFETCH_LOCK_STALE_SECONDS + 10)
    os.utime(lock_path, (stale_mtime, stale_mtime))

    backend_main._PREFETCH_LOCK_OWNED = False
    backend_main._PREFETCH_LOCK_PATH = None

    acquired = backend_main.acquire_prefetch_process_lock()
    assert acquired is True
    assert lock_path.exists() is True

    backend_main.release_prefetch_process_lock()
