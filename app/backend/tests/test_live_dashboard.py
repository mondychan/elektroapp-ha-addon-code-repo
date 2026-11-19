import datetime as dt
import logging

import pytest

from services.live_service import LiveSnapshotService


class Clock:
    """Deterministic now_fn / monotonic_fn pair for the TTL tests."""

    def __init__(self, hour=12, minute=0):
        self.hour = hour
        self.minute = minute
        self.monotonic = 0.0

    def __call__(self, tzinfo=None):
        from zoneinfo import ZoneInfo

        return dt.datetime(
            2026, 11, 18, self.hour, self.minute, 0, tzinfo=ZoneInfo("Europe/Prague")
        )

    def monotonic_fn(self):
        return self.monotonic


def make_service(clock, data_calls, battery_calls, ttl=0.85, fail_data=False, fail_battery=False):
    def get_live_data(*, cfg, tzinfo):
        data_calls.append(1)
        if fail_data:
            raise RuntimeError("influx down")
        return {
            "prices": [{"time": "12:00", "final": 3.0}],
            "alerts": {"current_price": 3.0},
        }

    def get_battery_live(*, cfg, tzinfo):
        battery_calls.append(1)
        if fail_battery:
            raise RuntimeError("influx down")
        return {"enabled": True, "status": {"soc_percent": 62.0}}

    def price_signature(prices, date_str):
        return (date_str, tuple((p.get("time"), p.get("final")) for p in prices))

    return LiveSnapshotService(
        get_live_data=get_live_data,
        get_battery_live=get_battery_live,
        price_signature=price_signature,
        now_fn=clock,
        monotonic_fn=clock.monotonic_fn,
        ttl_seconds=ttl,
        logger=logging.getLogger("test"),
    )


def test_snapshot_carries_prices_alerts_battery_and_server_time():
    service = make_service(Clock(), [], [])

    out = service.get_snapshot(cfg={}, tzinfo=None)

    assert out["date"] == "2026-11-18"
    assert out["current_slot"] == 48
    assert out["prices"][0]["final"] == 3.0
    assert out["alerts"]["current_price"] == 3.0
    assert out["battery"]["status"]["soc_percent"] == 62.0
    assert out["server_time"].startswith("2026-11-18T12:00:00+01:00")


def test_calls_inside_ttl_share_one_build():
    clock = Clock()
    data_calls, battery_calls = [], []
    service = make_service(clock, data_calls, battery_calls)

    for _ in range(5):
        clock.monotonic += 0.1
        service.get_snapshot(cfg={}, tzinfo=None)

    assert len(data_calls) == 1
    assert len(battery_calls) == 1


def test_slot_change_invalidates_the_cache():
    clock = Clock()
    data_calls, battery_calls = [], []
    service = make_service(clock, data_calls, battery_calls)

    service.get_snapshot(cfg={}, tzinfo=None)
    clock.minute = 15
    service.get_snapshot(cfg={}, tzinfo=None)

    assert len(data_calls) == 2
    assert len(battery_calls) == 2


def test_failing_prices_are_never_cached():
    clock = Clock()
    data_calls, battery_calls = [], []
    fail = {"on": True}

    def get_live_data(*, cfg, tzinfo):
        data_calls.append(1)
        if fail["on"]:
            raise RuntimeError("influx down")
        return {"prices": [{"time": "12:00", "final": 3.0}], "alerts": {}}

    def get_battery_live(*, cfg, tzinfo):
        battery_calls.append(1)
        return {"enabled": True}

    def price_signature(prices, date_str):
        return (date_str, tuple((p.get("time"), p.get("final")) for p in prices))

    service = LiveSnapshotService(
        get_live_data=get_live_data,
        get_battery_live=get_battery_live,
        price_signature=price_signature,
        now_fn=clock,
        monotonic_fn=clock.monotonic_fn,
        ttl_seconds=0.85,
    )

    with pytest.raises(RuntimeError):
        service.get_snapshot(cfg={}, tzinfo=None)

    # The failure was not stored, so the very next poll rebuilds.
    fail["on"] = False
    clock.monotonic += 0.1
    out = service.get_snapshot(cfg={}, tzinfo=None)
    assert out["prices"][0]["final"] == 3.0
    assert len(data_calls) == 2

    # ...and that successful build is cached like any other.
    clock.monotonic += 0.1
    service.get_snapshot(cfg={}, tzinfo=None)
    assert len(data_calls) == 2
    assert len(battery_calls) == 1


def test_battery_failure_does_not_break_the_price_payload():
    clock = Clock()
    data_calls, battery_calls = [], []
    service = make_service(clock, data_calls, battery_calls, fail_battery=True)

    out = service.get_snapshot(cfg={}, tzinfo=None)

    assert out["prices"][0]["final"] == 3.0
    assert out["battery"] is None
    assert len(battery_calls) == 1


def test_reset_drops_the_cached_payload():
    clock = Clock()
    data_calls, battery_calls = [], []
    service = make_service(clock, data_calls, battery_calls)

    service.get_snapshot(cfg={}, tzinfo=None)
    service.reset()
    service.get_snapshot(cfg={}, tzinfo=None)

    assert len(data_calls) == 2
    assert len(battery_calls) == 2


def test_concurrent_polls_build_once():
    """A dozen focused tabs must cause one battery read, not a stampede."""
    import threading

    clock = Clock()
    data_calls, battery_calls = [], []
    build_started = threading.Event()
    release_build = threading.Event()

    def get_live_data(*, cfg, tzinfo):
        data_calls.append(1)
        build_started.set()
        release_build.wait(timeout=5)
        return {"prices": [{"time": "12:00", "final": 3.0}], "alerts": {}}

    def get_battery_live(*, cfg, tzinfo):
        battery_calls.append(1)
        return {"enabled": True}

    service = LiveSnapshotService(
        get_live_data=get_live_data,
        get_battery_live=get_battery_live,
        price_signature=lambda prices, date_str: (date_str, len(prices)),
        now_fn=clock,
        monotonic_fn=clock.monotonic_fn,
        ttl_seconds=0.85,
    )

    results = []

    def poll():
        results.append(service.get_snapshot(cfg={}, tzinfo=None))

    threads = [threading.Thread(target=poll) for _ in range(8)]
    for thread in threads:
        thread.start()
    build_started.wait(timeout=5)
    clock.monotonic += 0.1  # inside the leader's TTL by the time it finishes
    release_build.set()
    for thread in threads:
        thread.join(timeout=5)

    # Exactly one build: the waiters block on the build lock and the
    # double-check sends them to the leader's entry.  Nothing may hang.
    assert len(results) == 8
    assert len(data_calls) == 1
    assert len(battery_calls) == 1
    assert all(result["prices"][0]["final"] == 3.0 for result in results)



def test_live_router_passes_request_context(monkeypatch):
    import asyncio
    from zoneinfo import ZoneInfo

    from dependencies import RequestContext
    from routers import api_router

    captured = {}

    async def fake_get_live_dashboard(*, cfg=None, tzinfo=None):
        captured["cfg"] = cfg
        captured["tzinfo"] = tzinfo
        return {"ok": True}

    monkeypatch.setattr(api_router.svc, "get_live_dashboard", fake_get_live_dashboard)
    ctx = RequestContext(
        config={"influxdb": {"timezone": "Europe/Prague"}},
        tzinfo=ZoneInfo("Europe/Prague"),
    )

    result = asyncio.run(api_router.get_live_dashboard(ctx=ctx))

    assert result == {"ok": True}
    assert captured["cfg"] == ctx.config
    assert captured["tzinfo"] == ctx.tzinfo
