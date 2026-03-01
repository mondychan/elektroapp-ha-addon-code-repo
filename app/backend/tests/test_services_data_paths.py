from zoneinfo import ZoneInfo

from services.costs_service import CostsService
from services.export_service import ExportService


def test_costs_service_uses_utc_fallback_without_local_iso_parsing():
    tzinfo = ZoneInfo("Europe/Prague")
    consumption = {
        "range": {"start": "2026-02-19T23:00:00Z", "end": "2026-02-20T23:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.import",
        "points": [
            {
                # Intentionally not ISO to ensure local parsing is not required.
                "time": "bad-local-time",
                "time_utc": "2026-02-20T00:15:00Z",
                "kwh": 1.5,
            }
        ],
        "tzinfo": tzinfo,
        "has_series": True,
        "from_cache": False,
        "cache_fallback": False,
    }
    price_map = {}
    price_map_utc = {"2026-02-20 00:15": {"spot": 2.0, "final": 3.0}}

    service = CostsService(
        get_consumption_points=lambda cfg, date, start, end: consumption,
        build_price_map_for_date=lambda cfg, date, tz: (price_map, price_map_utc),
    )

    data = service.get_costs(date="2026-02-20", start=None, end=None, cfg={}, tzinfo=tzinfo)

    assert data["summary"]["kwh_total"] == 1.5
    assert data["summary"]["cost_total"] == 4.5
    assert data["points"][0]["final_price"] == 3.0
    assert data["points"][0]["cost"] == 4.5


def test_export_service_uses_utc_fallback_without_local_iso_parsing():
    tzinfo = ZoneInfo("Europe/Prague")
    export = {
        "range": {"start": "2026-02-19T23:00:00Z", "end": "2026-02-20T23:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.export",
        "points": [
            {
                "time": "bad-local-time",
                "time_utc": "2026-02-20T00:15:00Z",
                "kwh": 2.0,
            }
        ],
        "tzinfo": tzinfo,
        "has_series": True,
        "from_cache": False,
        "cache_fallback": False,
    }
    price_map = {}
    price_map_utc = {"2026-02-20 00:15": {"spot": 2.5, "final": 3.5}}

    service = ExportService(
        get_export_points=lambda cfg, date, start, end: export,
        build_price_map_for_date=lambda cfg, date, tz: (price_map, price_map_utc),
        get_fee_snapshot_for_date=lambda cfg, date, tz: {},
        get_sell_coefficient_kwh=lambda cfg, snapshot: 0.5,
    )

    data = service.get_export(date="2026-02-20", start=None, end=None, cfg={}, tzinfo=tzinfo)

    assert data["summary"]["export_kwh_total"] == 2.0
    assert data["summary"]["sell_total"] == 4.0
    assert data["points"][0]["spot_price"] == 2.5
    assert data["points"][0]["sell_price"] == 2.0
    assert data["points"][0]["sell"] == 4.0
