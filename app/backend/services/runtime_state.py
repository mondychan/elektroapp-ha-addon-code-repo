import threading
import os
import time as time_module
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

class RuntimeState:
    def __init__(self):
        # OTE state
        self.ote_unavailable_until: Optional[float] = None
        
        # Prefetch scheduler state
        self.prefetch_thread: Optional[threading.Thread] = None
        self.prefetch_thread_guard = threading.Lock()
        self.prefetch_lock_owned = False
        self.prefetch_lock_path: Optional[Path] = None

        # PND scheduler state
        self.pnd_thread: Optional[threading.Thread] = None
        self.pnd_thread_guard = threading.Lock()
        self.pnd_lock_owned = False
        self.pnd_lock_path: Optional[Path] = None

    def mark_ote_unavailable(self, retry_seconds: int):
        self.ote_unavailable_until = time_module.time() + retry_seconds

    def is_ote_unavailable(self) -> bool:
        if self.ote_unavailable_until is None:
            return False
        if time_module.time() > self.ote_unavailable_until:
            self.ote_unavailable_until = None
            return False
        return True

    def get_ote_backoff_remaining_seconds(self) -> int:
        if not self.is_ote_unavailable():
            return 0
        return int(max(0, self.ote_unavailable_until - time_module.time()))
