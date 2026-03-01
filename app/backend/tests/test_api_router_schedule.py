from routers import api_router
from dependencies import RequestContext
from zoneinfo import ZoneInfo


def test_schedule_router_forwards_duration_and_count(monkeypatch):
    captured = {}
    ctx = RequestContext(config={"influxdb": {"timezone": "Europe/Prague"}}, tzinfo=ZoneInfo("Europe/Prague"))

    def fake_get_schedule(*, duration, count, cfg=None, tzinfo=None):
        captured["duration"] = duration
        captured["count"] = count
        captured["cfg"] = cfg
        captured["tzinfo"] = tzinfo
        return {"ok": True}

    monkeypatch.setattr(api_router.svc, "get_schedule", fake_get_schedule)

    result = api_router.get_schedule(duration=150, count=2, ctx=ctx)

    assert result == {"ok": True}
    assert captured["duration"] == 150
    assert captured["count"] == 2
    assert captured["cfg"] == ctx.config
    assert captured["tzinfo"] == ctx.tzinfo


def test_schedule_router_accepts_legacy_duration_minutes(monkeypatch):
    captured = {}
    ctx = RequestContext(config={"influxdb": {"timezone": "Europe/Prague"}}, tzinfo=ZoneInfo("Europe/Prague"))

    def fake_get_schedule(*, duration, count, cfg=None, tzinfo=None):
        captured["duration"] = duration
        captured["count"] = count
        captured["cfg"] = cfg
        captured["tzinfo"] = tzinfo
        return {"ok": True}

    monkeypatch.setattr(api_router.svc, "get_schedule", fake_get_schedule)

    result = api_router.get_schedule(duration=120, count=3, duration_minutes=45, date="2026-02-28", ctx=ctx)

    assert result == {"ok": True}
    assert captured["duration"] == 45
    assert captured["count"] == 3
    assert captured["cfg"] == ctx.config
    assert captured["tzinfo"] == ctx.tzinfo
