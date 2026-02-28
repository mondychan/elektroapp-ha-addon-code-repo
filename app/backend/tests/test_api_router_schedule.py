from routers import api_router


def test_schedule_router_forwards_duration_and_count(monkeypatch):
    captured = {}

    def fake_get_schedule(*, duration, count):
        captured["duration"] = duration
        captured["count"] = count
        return {"ok": True}

    monkeypatch.setattr(api_router.svc, "get_schedule", fake_get_schedule)

    result = api_router.get_schedule(duration=150, count=2)

    assert result == {"ok": True}
    assert captured == {"duration": 150, "count": 2}


def test_schedule_router_accepts_legacy_duration_minutes(monkeypatch):
    captured = {}

    def fake_get_schedule(*, duration, count):
        captured["duration"] = duration
        captured["count"] = count
        return {"ok": True}

    monkeypatch.setattr(api_router.svc, "get_schedule", fake_get_schedule)

    result = api_router.get_schedule(duration=120, count=3, duration_minutes=45, date="2026-02-28")

    assert result == {"ok": True}
    assert captured == {"duration": 45, "count": 3}
