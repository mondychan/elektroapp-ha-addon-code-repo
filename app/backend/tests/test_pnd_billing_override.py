from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import app_service as svc


class _FakePNDDay:
    def __init__(self, date_str, consumption_kwh, production_kwh):
        self.date_str = date_str
        intervals = []
        base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Europe/Prague"))
        # 4 x 15-min intervals (just to exercise iteration + per-kWh math)
        for i in range(4):
            start = base + timedelta(minutes=15 * i)
            end = start + timedelta(minutes=15)
            consumption_kwh = consumption_kwh / 4.0
            production_kwh = production_kwh / 4.0
            intervals.append(
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "consumption_kwh": round(consumption_kwh, 6),
                    "production_kwh": round(production_kwh, 6),
                }
            )
        self.payload = {
            "date": date_str,
            "source": "pnd-cez",
            "interval_minutes": 15,
            "intervals": intervals,
            "totals": {
                "consumption_kwh": consumption_kwh,
                "production_kwh": production_kwh,
            },
        }

    def get_data(self, from_date, to_date):
        return {"from": from_date, "to": to_date, "days": [self.payload], "days_count": 1}


class _FakePNDService:
    def __init__(self, day):
        self._day = day

    def has_day(self, date_str):
        return date_str == self._day.date_str

    def get_data(self, from_date, to_date):
        return self._day.get_data(from_date, to_date)


def _reset(pnd_service):
    saved = svc.PND_SERVICE
    svc.PND_SERVICE = pnd_service
    try:
        yield
    finally:
        svc.PND_SERVICE = saved


def test_get_consumption_points_uses_pnd_when_available():
    tzinfo = ZoneInfo("Europe/Prague")
    day = _FakePNDDay("2026-06-19", 10.776, 7.594)
    with _reset(_FakePNDService(day)):
        result = svc.get_consumption_points(
            cfg={"influxdb": {"timezone": "Europe/Prague"}},
            date="2026-06-19",
        )
    assert result["source"] == "pnd", result
    assert result["has_series"] is True
    assert abs(result["range"]["start"] - "2026-06-19T00:00:00+02:00") < timedelta(seconds=1)
    total = sum(p["kwh"] for p in result["points"])
    assert abs(total - 10.776) < 1e-3, total
    # Per-kWh shape used by BillingService
    assert all("time" in p and "time_utc" in p and "kwh" in p for p in result["points"])


def test_get_export_points_uses_pnd_when_available():
    day = _FakePNDDay("2026-06-19", 10.776, 7.594)
    with _reset(_FakePNDService(day)):
        result = svc.get_export_points(
            cfg={"influxdb": {"timezone": "Europe/Prague"}},
            date="2026-06-19",
        )
    assert result["source"] == "pnd", result
    assert result["has_series"] is True
    total = sum(p["kwh"] for p in result["points"])
    assert abs(total - 7.594) < 1e-3, total


def test_get_consumption_points_falls_back_to_influx_without_pnd():
    tzinfo = ZoneInfo("Europe/Prague")
    called = {}

    def fake_get_consumption_points(cfg, influx_service, consumption_cache, get_influx_cfg_fn, get_total_tz_fn, date=None, start=None, end=None, cache_ttl=600):
        called["yes"] = True
        return {
            "range": {"start": "2026-06-19T00:00:00+02:00", "end": "2026-06-20T00:00:00+02:00"},
            "interval": "15m",
            "entity_id": "sensor.import",
            "points": [{"time": "2026-06-19T00:00:00+02:00", "time_utc": "2026-06-18T22:00:00Z", "kwh_total": None, "kwh": 4.45}],
            "tzinfo": tzinfo,
            "has_series": True,
            "from_cache": False,
            "cache_fallback": False,
        }

    day = _FakePNDDay("2026-06-20", 10.460, 1.748)  # a DIFFERENT day
    with _reset(_FakePNDService(day)):
        # Monkeypatch the inner import target.
        import services.consumption_service as cs
        orig = cs.get_consumption_points
        cs.get_consumption_points = fake_get_consumption_points
        try:
            result = svc.get_consumption_points(
                cfg={"influxdb": {"timezone": "Europe/Prague"}},
                date="2026-06-19",  # not a PND day
            )
        finally:
            cs.get_consumption_points = orig
    assert called.get("yes") is True
    assert result["source"] != "pnd", result
    assert result["points"][0]["kwh"] == 4.45
