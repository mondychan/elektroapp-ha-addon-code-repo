from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import threading
import time as time_module


@dataclass
class RuntimeState:
    prefetch_thread: object | None = None
    prefetch_thread_guard: threading.Lock = field(default_factory=threading.Lock)
    prefetch_lock_owned: bool = False
    prefetch_lock_path: Path | None = None
    ote_unavailable_until_ts: float = 0.0

    def mark_ote_unavailable(self, retry_seconds: int):
        self.ote_unavailable_until_ts = max(
            self.ote_unavailable_until_ts,
            time_module.time() + max(0, int(retry_seconds)),
        )

    def get_ote_backoff_remaining_seconds(self) -> int:
        remaining = int(self.ote_unavailable_until_ts - time_module.time())
        return max(0, remaining)

    def is_ote_unavailable(self) -> bool:
        return self.get_ote_backoff_remaining_seconds() > 0
