import time
from zoneinfo import ZoneInfo

from services.costs_service import CostsService
from services.export_service import ExportService


def _build_points(count):
    points = []
    for idx in range(count):
        hour = (idx // 4) % 24
        minute = (idx % 4) * 15
        day = 20 + (idx // 96)
        points.append(
            {
                "time": f"2026-02-{day:02d}T{hour:02d}:{minute:02d}:00+01:00",
                "time_utc": f"2026-02-{day:02d}T{hour:02d}:{minute:02d}:00Z",
                "kwh": 0.25,
            }
        )
    return points


def test_costs_service_large_payload_stays_fast():
    tzinfo = ZoneInfo("Europe/Prague")
    points = _build_points(5000)
    consumption = {
        "range": {"start": "2026-02-20T00:00:00Z", "end": "2026-02-21T00:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.import",
        "points": points,
        "tzinfo": tzinfo,
        "has_series": True,
        "from_cache": False,
        "cache_fallback": False,
    }
    price_map = {f"{p['time'][:10]} {p['time'][11:16]}": {"spot": 2.0, "final": 3.0} for p in points}

    service = CostsService(
        get_consumption_points=lambda cfg, date, start, end: consumption,
        build_price_map_for_date=lambda cfg, date, tz: (price_map, price_map),
    )

    start_ts = time.perf_counter()
    result = service.get_costs(date="2026-02-20", start=None, end=None, cfg={}, tzinfo=tzinfo)
    elapsed = time.perf_counter() - start_ts

    assert result["summary"]["kwh_total"] == 1250.0
    assert elapsed < 1.5


def test_export_service_large_payload_stays_fast():
    tzinfo = ZoneInfo("Europe/Prague")
    points = _build_points(5000)
    export = {
        "range": {"start": "2026-02-20T00:00:00Z", "end": "2026-02-21T00:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.export",
        "points": points,
        "tzinfo": tzinfo,
        "has_series": True,
        "from_cache": False,
        "cache_fallback": False,
    }
    price_map = {f"{p['time'][:10]} {p['time'][11:16]}": {"spot": 2.0, "final": 3.0} for p in points}

    service = ExportService(
        get_export_points=lambda cfg, date, start, end: export,
        build_price_map_for_date=lambda cfg, date, tz: (price_map, price_map),
        get_fee_snapshot_for_date=lambda cfg, date, tz: {},
        get_sell_coefficient_kwh=lambda cfg, snapshot: 0.5,
    )

    start_ts = time.perf_counter()
    result = service.get_export(date="2026-02-20", start=None, end=None, cfg={}, tzinfo=tzinfo)
    elapsed = time.perf_counter() - start_ts

    assert result["summary"]["export_kwh_total"] == 1250.0
    assert elapsed < 1.5
