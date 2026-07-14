from contextlib import contextmanager
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import app_service as svc


class _FakePNDDay:
    def __init__(self, date_str, imp_kwh, exp_kwh):
        self.date_str = date_str
        base = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=ZoneInfo("Europe/Prague"))
        n = 4  # intervals per day
        intervals = []
        for i in range(n):
            start = base + timedelta(minutes=15 * i)
            end = start + timedelta(minutes=15)
            intervals.append(
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "consumption_kwh": round(imp_kwh / n, 6),
                    "production_kwh": round(exp_kwh / n, 6),
                }
            )
        self.payload = {
            "date": date_str,
            "source": "pnd-cez",
            "interval_minutes": 15,
            "intervals": intervals,
            "totals": {"consumption_kwh": imp_kwh, "production_kwh": exp_kwh},
        }

    def get_data(self, from_date, to_date):
        return {"days": [self.payload], "days_count": 1}


class _FakePNDService:
    def __init__(self, day):
        self._day = day

    def has_day(self, date_str):
        return date_str == self._day.date_str

    def get_data(self, from_date, to_date):
        return self._day.get_data(from_date, to_date)


@contextmanager
def _pnd_env(service):
    saved = svc.PND_SERVICE
    svc.PND_SERVICE = service
    try:
        yield
    finally:
        svc.PND_SERVICE = saved


def test_get_consumption_points_uses_pnd_when_available():
    day = _FakePNDDay("2026-06-19", 10.776, 7.594)
    with _pnd_env(_FakePNDService(day)):
        result = svc.get_consumption_points(
            cfg={"influxdb": {"timezone": "Europe/Prague"}},
            date="2026-06-19",
        )
    assert result["source"] == "pnd", result
    assert result["has_series"] is True
    total = round(sum(p["kwh"] for p in result["points"]), 3)
    assert total == 10.776, total
    assert all("time" in p and "time_utc" in p and "kwh" in p for p in result["points"])


def test_get_export_points_uses_pnd_when_available():
    day = _FakePNDDay("2026-06-19", 10.776, 7.594)
    with _pnd_env(_FakePNDService(day)):
        result = svc.get_export_points(
            cfg={"influxdb": {"timezone": "Europe/Prague"}},
            date="2026-06-19",
        )
    assert result["source"] == "pnd", result
    assert result["has_series"] is True
    total = round(sum(p["kwh"] for p in result["points"]), 3)
    assert total == 7.594, total


def test_get_consumption_points_falls_back_to_influx_without_pnd():
    called = {}

    def fake_influx_points(*a, **k):
        called["yes"] = True
        return {
            "range": {"start": "2026-06-19T00:00:00+02:00", "end": "2026-06-20T00:00:00+02:00"},
            "interval": "15m",
            "entity_id": "sensor.import",
            "points": [{"time": "2026-06-19T00:00:00+02:00", "time_utc": "2026-06-18T22:00:00Z", "kwh_total": None, "kwh": 4.45}],
            "tzinfo": ZoneInfo("Europe/Prague"),
            "has_series": True,
            "from_cache": False,
            "cache_fallback": False,
        }

    # PND has data for day 20, we query day 19 → should skip PND and fall to Influx
    day = _FakePNDDay("2026-06-20", 10.460, 1.748)
    with _pnd_env(_FakePNDService(day)):
        import services.consumption_service as cs
        orig = cs.get_consumption_points
        cs.get_consumption_points = fake_influx_points
        try:
            result = svc.get_consumption_points(
                cfg={"influxdb": {"timezone": "Europe/Prague"}},
                date="2026-06-19",
            )
        finally:
            cs.get_consumption_points = orig
    assert called.get("yes") is True
    assert result.get("source") != "pnd"
    assert result["points"][0]["kwh"] == 4.45
