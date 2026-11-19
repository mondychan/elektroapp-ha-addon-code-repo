from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Callable


class LiveSnapshotService:
    """1 Hz dashboard payload behind a small TTL, single-flight cache.

    The heavy ``/api/dashboard-snapshot`` keeps owning history, projections and
    cost totals.  This service refreshes only what visibly moves second to
    second: the active price slot, its alerts, and instantaneous battery/PV
    power.

    Why a cache at all: every focused browser tab polls at 1 Hz, and one battery
    read costs a handful of InfluxDB queries.  Without a shared cache ten tabs
    would multiply that load ten times over.

    The entries are keyed by ``(date, slot)`` and expire after a short TTL, so
    all polls inside the same window share one result.  Callers that change
    prices (a manual refresh, a fee-history edit) call :meth:`reset` to
    drop it immediately.  The ``price_signature`` field in the payload is not
    part of the lookup key: it is computed after the build and shipped to
    clients so they can skip re-rendering when nothing moved.

    Price failures are never cached.  Battery is optional telemetry, so a
    battery failure is logged and cached as ``battery: None`` for the rest of
    the TTL while prices and alerts are still served.
    """

    def __init__(
        self,
        *,
        get_live_data: Callable[..., dict[str, Any]],
        get_battery_live: Callable[..., dict[str, Any]],
        price_signature: Callable[[Any, str], Any],
        now_fn: Callable[..., datetime] = datetime.now,
        monotonic_fn: Callable[[], float] = time.monotonic,
        ttl_seconds: float = 0.85,
        logger=None,
    ):
        self._get_live_data = get_live_data
        self._get_battery_live = get_battery_live
        self._price_signature = price_signature
        self._now_fn = now_fn
        self._monotonic_fn = monotonic_fn
        self._ttl_seconds = max(0.0, float(ttl_seconds))
        self._logger = logger

        self._lock = threading.Lock()
        # Held for the whole build so concurrent polls of an expired entry wait
        # for one leader instead of stampeding InfluxDB.  Never held on the fast
        # path, so a slow query cannot block polls that are already served.
        self._build_lock = threading.Lock()
        self._cache_key: Any = None
        self._cached_at = 0.0
        self._cached_payload: dict[str, Any] | None = None

    def _now(self, tzinfo=None) -> datetime:
        if tzinfo is not None:
            return self._now_fn(tzinfo)
        return self._now_fn()

    def reset(self) -> None:
        """Drop the cache; used by tests and configuration reloads."""
        with self._lock:
            self._cache_key = None
            self._cached_at = 0.0
            self._cached_payload = None

    def get_snapshot(self, *, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        now = self._now(tzinfo)
        date_str = now.strftime("%Y-%m-%d")
        current_slot = int((now.hour * 60 + now.minute) / 15)
        cache_key = (date_str, current_slot)
        checked_at = self._monotonic_fn()

        # Fast path: same slot and an unexpired entry.  Nothing to rebuild, so
        # the lock is only held long enough to copy the payload out.
        with self._lock:
            if (
                self._cached_payload is not None
                and self._cache_key == cache_key
                and checked_at - self._cached_at < self._ttl_seconds
            ):
                return self._present(self._cached_payload, now)

        # Single flight: one tab rebuilds, the rest wait and then reuse the fresh
        # entry.  The second check matters because a waiter may find that the
        # leader already rebuilt the very same slot.
        with self._build_lock:
            built_at = self._monotonic_fn()
            with self._lock:
                if (
                    self._cached_payload is not None
                    and self._cache_key == cache_key
                    and built_at - self._cached_at < self._ttl_seconds
                ):
                    return self._present(self._cached_payload, now)

            live = self._get_live_data(cfg=cfg, tzinfo=tzinfo)
            prices = live.get("prices") or []
            alerts = live.get("alerts") or {}
            signature = self._price_signature(prices, date_str)

            battery = None
            try:
                battery = self._get_battery_live(cfg=cfg, tzinfo=tzinfo)
            except Exception as exc:  # battery is optional telemetry
                if self._logger is not None:
                    self._logger.warning("Live battery read failed: %s", exc)

            payload = {
                "date": date_str,
                "current_slot": current_slot,
                "prices": prices,
                "alerts": alerts,
                "battery": battery,
                "price_signature": signature,
            }

            with self._lock:
                self._cache_key = cache_key
                self._cached_at = self._monotonic_fn()
                self._cached_payload = payload
            return self._present(payload, now)

    @staticmethod
    def _present(payload: dict[str, Any], now: datetime) -> dict[str, Any]:
        result = dict(payload)
        result["server_time"] = now.isoformat()
        result["server_epoch_ms"] = int(now.timestamp() * 1000)
        return result
