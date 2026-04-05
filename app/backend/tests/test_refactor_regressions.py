from zoneinfo import ZoneInfo

from fastapi import HTTPException

from services.energy_balance_service import aggregate_power_points
from services.energy_balance_service import build_energy_balance_range
from services.insights_service import InsightsService
from services.price_fetcher import build_price_map_for_date


def test_build_price_map_for_date_supports_keyword_only_getters():
    tzinfo = ZoneInfo("Europe/Prague")
    entries = [{"time": "2026-04-05 00:15", "spot": 1.25, "final": 2.5}]

    def get_prices(*, cfg, date, tzinfo):
        assert cfg == {"source": "test"}
        assert date == "2026-04-05"
        assert tzinfo.key == "Europe/Prague"
        return entries

    price_map, price_map_utc = build_price_map_for_date({"source": "test"}, "2026-04-05", tzinfo, get_prices)

    assert price_map["2026-04-05 00:15"]["final"] == 2.5
    assert price_map_utc["2026-04-04 22:15"]["spot"] == 1.25


def test_build_price_map_for_date_supports_legacy_positional_getters():
    tzinfo = ZoneInfo("Europe/Prague")
    entries = [{"time": "2026-04-05 13:30", "spot": 0.95, "final": 1.8}]

    def get_prices(cfg, date, tzinfo):
        assert cfg == {"source": "legacy"}
        assert date == "2026-04-05"
        assert tzinfo.key == "Europe/Prague"
        return entries

    price_map, _ = build_price_map_for_date({"source": "legacy"}, "2026-04-05", tzinfo, get_prices)

    assert price_map["2026-04-05 13:30"]["final"] == 1.8


def test_aggregate_power_points_groups_daily_kwh_from_watts():
    tzinfo = ZoneInfo("Europe/Prague")
    points = [
        {"time": "2026-04-05T08:00:00+02:00", "value": 1000},
        {"time": "2026-04-05T08:15:00+02:00", "value": 1000},
        {"time": "2026-04-05T08:30:00+02:00", "value": 1000},
        {"time": "2026-04-05T08:45:00+02:00", "value": 1000},
        {"time": "2026-04-06T09:00:00+02:00", "value": 500},
    ]

    aggregated = aggregate_power_points(points, 15, bucket="day", tzinfo=tzinfo)

    assert aggregated == {
        "2026-04-05": 1.0,
        "2026-04-06": 0.125,
    }


def test_aggregate_power_points_groups_monthly_kwh_from_kw():
    tzinfo = ZoneInfo("Europe/Prague")
    points = [
        {"time": "2026-03-10T12:00:00+01:00", "value": 2.0},
        {"time": "2026-03-10T12:30:00+01:00", "value": 2.0},
        {"time_utc": "2026-04-01T10:00:00Z", "value": 1.5},
    ]

    aggregated = aggregate_power_points(points, 30, bucket="month", tzinfo=tzinfo)

    assert aggregated == {
        "2026-03": 2.0,
        "2026-04": 0.75,
    }


def test_build_energy_balance_range_uses_month_anchor():
    tzinfo = ZoneInfo("Europe/Prague")

    result = build_energy_balance_range("month", "2026-02", tzinfo)

    assert result["start_local"].strftime("%Y-%m-%d") == "2026-02-01"
    assert result["end_local"].strftime("%Y-%m-%d") == "2026-03-01"


def test_insights_service_degrades_when_one_entity_query_fails():
    tzinfo = ZoneInfo("Europe/Prague")

    def query_entity_series(_influx, entity_id, *_args, **_kwargs):
        if entity_id == "sensor.bad":
            raise HTTPException(status_code=500, detail="boom")
        return [
            {"time": "2026-04-07T00:00:00+02:00", "value": 1000},
            {"time": "2026-04-07T00:15:00+02:00", "value": 1000},
        ]

    service = InsightsService(
        get_influx_cfg=lambda cfg: {"interval": "15m", **cfg},
        get_energy_entities_cfg=lambda cfg: {
            "pv_power_total_entity_id": "sensor.ok",
            "house_load_power_entity_id": "sensor.bad",
            "grid_import_power_entity_id": None,
            "grid_export_power_entity_id": None,
        },
        build_energy_balance_range=build_energy_balance_range,
        parse_influx_interval_to_minutes=lambda interval, default_minutes=15: 15,
        query_entity_series=query_entity_series,
        aggregate_power_points=aggregate_power_points,
        build_energy_balance_buckets=lambda range_info, _tz: [
            {"key": "2026-04-07", "label": "07.04.", "start": range_info["start_local"].isoformat()}
        ],
        get_prices_for_date=lambda *args, **kwargs: [],
        aggregate_hourly_from_price_entries=lambda entries: [],
        get_consumption_points=lambda *args, **kwargs: {},
        get_export_points=lambda *args, **kwargs: {},
        aggregate_hourly_from_kwh_points=lambda points: [],
        logger=type("Logger", (), {"warning": lambda *args, **kwargs: None})(),
    )

    result = service.get_energy_balance(period="week", anchor="2026-04-07", cfg={}, tzinfo=tzinfo)

    assert result["partial"] is True
    assert result["totals"]["pv_kwh"] == 0.5
    assert result["totals"]["house_load_kwh"] == 0.0
    assert result["diagnostics"]["pv_kwh"]["status"] == "ok"
    assert result["diagnostics"]["house_load_kwh"]["status"] == "error"
