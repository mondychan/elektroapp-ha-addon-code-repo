import json

from datetime import datetime

from services.solar_service import SolarService


def _forecast_cfg(**overrides):
    return {
        "enabled": True,
        "power_now_entity_id": "sensor.forecast_power_now",
        "power_next_hour_entity_id": "sensor.forecast_power_next_hour",
        "power_next_12hours_entity_id": "sensor.forecast_power_next_12hours",
        "power_next_24hours_entity_id": "sensor.forecast_power_next_24hours",
        "energy_current_hour_entity_id": "sensor.forecast_energy_current_hour",
        "energy_next_hour_entity_id": "sensor.forecast_energy_next_hour",
        "energy_production_today_entity_id": "sensor.forecast_today",
        "energy_production_today_remaining_entity_id": "sensor.forecast_remaining",
        "energy_production_tomorrow_entity_id": "sensor.forecast_tomorrow",
        "power_highest_peak_time_today_entity_id": "sensor.peak_today",
        "power_highest_peak_time_tomorrow_entity_id": "sensor.peak_tomorrow",
        **overrides,
    }


def test_solar_service_uses_measurement_candidates_by_metric(tmp_path):
    calls = []

    def safe_query(_influx, entity_id, **kwargs):
        calls.append((entity_id, kwargs))
        if kwargs.get("numeric", True):
            return {"value": 1.23}
        return {"raw_value": "2026-04-05T12:00:00+02:00"}

    service = SolarService(
        get_influx_cfg_fn=lambda cfg: {"measurement": "kWh", "timezone": "Europe/Prague", **cfg},
        get_forecast_solar_cfg_fn=lambda cfg: _forecast_cfg(),
        safe_query_entity_last_value_fn=safe_query,
        get_energy_entities_cfg_fn=lambda cfg: {"pv_power_total_entity_id": None},
        history_file_path_fn=lambda: tmp_path / "solar-history.json",
        now_fn=lambda tzinfo=None: datetime(2026, 4, 5, 12, 0, tzinfo=tzinfo),
        history_backfill_days=0,
    )

    data = service.get_solar_forecast({})

    assert data["enabled"] is True
    assert data["status"]["power_now"] == 1.23
    assert data["status"]["power_next_hour"] == 1.23
    assert data["status"]["energy_current_hour"] == 1.23
    assert data["status"]["production_today"] == 1.23
    assert data["status"]["peak_today"] == "2026-04-05T12:00:00+02:00"
    assert data["status"]["peak_time_today_hhmm"] == "12:00"

    by_entity = {entity_id: kwargs for entity_id, kwargs in calls}
    assert by_entity["sensor.forecast_power_now"]["measurement_candidates"] == ["W", "kW"]
    assert by_entity["sensor.forecast_power_next_hour"]["measurement_candidates"] == ["W", "kW"]
    assert by_entity["sensor.forecast_energy_current_hour"]["measurement_candidates"] == ["kWh", "Wh"]
    assert by_entity["sensor.forecast_today"]["measurement_candidates"] == ["kWh", "Wh"]
    assert by_entity["sensor.peak_today"]["measurement_candidates"] == ["state"]


def test_solar_service_returns_v2_actuals_and_adjusted_totals(tmp_path):
    history_path = tmp_path / "solar-history.json"
    history_path.write_text(
        json.dumps(
            {
                "2026-04-03": {"actual_total_kwh": 8.0, "forecast_total_kwh": 10.0},
                "2026-04-04": {"actual_total_kwh": 9.0, "forecast_total_kwh": 10.0},
            }
        ),
        encoding="utf-8",
    )

    def safe_query(_influx, entity_id, **kwargs):
        values = {
            "sensor.forecast_power_now": {"value": 2500.0},
            "sensor.forecast_power_next_hour": {"value": 1800.0},
            "sensor.forecast_power_next_12hours": {"value": 1500.0},
            "sensor.forecast_power_next_24hours": {"value": 400.0},
            "sensor.forecast_energy_current_hour": {"value": 1.5},
            "sensor.forecast_energy_next_hour": {"value": 2.0},
            "sensor.forecast_today": {"value": 12.0},
            "sensor.forecast_remaining": {"value": 7.0},
            "sensor.forecast_tomorrow": {"value": 14.0},
            "sensor.actual_pv": {"value": 2200.0},
        }
        return values.get(entity_id)

    def query_series(_influx, entity_id, *_args, **_kwargs):
        assert entity_id == "sensor.actual_pv"
        return [
            {"time": "2026-04-05T09:00:00+02:00", "time_utc": "2026-04-05T07:00:00Z", "value": 2000.0, "unit": "W"},
            {"time": "2026-04-05T09:15:00+02:00", "time_utc": "2026-04-05T07:15:00Z", "value": 3000.0, "unit": "W"},
        ]

    def aggregate_power_points(points, interval_minutes=15, bucket="day", tzinfo=None):
        assert interval_minutes == 15
        assert bucket == "day"
        assert tzinfo is not None
        assert len(points) == 2
        return {"2026-04-05": 5.0}

    service = SolarService(
        get_influx_cfg_fn=lambda cfg: {
            "field": "value",
            "measurement": "kWh",
            "interval": "15m",
            "timezone": "Europe/Prague",
            **cfg,
        },
        get_forecast_solar_cfg_fn=lambda cfg: _forecast_cfg(),
        safe_query_entity_last_value_fn=safe_query,
        get_energy_entities_cfg_fn=lambda cfg: {"pv_power_total_entity_id": "sensor.actual_pv"},
        query_entity_series_fn=query_series,
        parse_influx_interval_to_minutes_fn=lambda interval, default_minutes=15: 15,
        aggregate_power_points_fn=aggregate_power_points,
        history_file_path_fn=lambda: history_path,
        now_fn=lambda tzinfo=None: datetime(2026, 4, 5, 12, 0, tzinfo=tzinfo),
        history_backfill_days=0,
    )

    data = service.get_solar_forecast({})

    assert data["comparison"]["model_version"] == "v2_hourly_bias"
    assert data["actual"]["power_now_w"] == 2200.0
    assert data["actual"]["production_today_kwh"] == 5.0
    assert data["comparison"]["forecast_so_far_kwh"] == 5.0
    assert data["comparison"]["historical_bias_ratio"] == 0.85
    assert data["comparison"]["remaining_hourly_bias_ratio"] == 0.85
    assert data["comparison"]["live_ratio"] == 1.0
    assert data["comparison"]["effective_bias_ratio"] == 0.91
    assert data["comparison"]["adjusted_projection_today_kwh"] == 11.37
    assert data["comparison"]["adjusted_projection_tomorrow_kwh"] == 11.9
    assert data["comparison"]["adjusted_current_hour_kwh"] == 1.275
    assert data["comparison"]["adjusted_next_hour_kwh"] == 1.7
    assert data["comparison"]["future_profile_source"] == "live_anchors_plus_historical_shape"
    assert data["status"]["power_production_next_hour_w"] == 1800.0
    assert len(data["status"]["power_production_next_12hours_w_by_hour"]) == 12
    assert len(data["status"]["power_production_next_24hours_w_by_hour"]) == 24


def test_solar_service_backfills_daily_and_hourly_history_from_influx(tmp_path):
    history_path = tmp_path / "solar-history.json"

    def safe_query(_influx, entity_id, **kwargs):
        values = {
            "sensor.forecast_power_now": {"value": 2500.0},
            "sensor.forecast_power_next_hour": {"value": 1800.0},
            "sensor.forecast_power_next_12hours": {"value": 1500.0},
            "sensor.forecast_power_next_24hours": {"value": 400.0},
            "sensor.forecast_energy_current_hour": {"value": 1.5},
            "sensor.forecast_energy_next_hour": {"value": 2.0},
            "sensor.forecast_today": {"value": 12.0},
            "sensor.forecast_remaining": {"value": 7.0},
            "sensor.forecast_tomorrow": {"value": 14.0},
            "sensor.actual_pv": {"value": 2200.0},
        }
        return values.get(entity_id)

    def query_series(_influx, entity_id, start_utc, end_utc, **_kwargs):
        assert start_utc < end_utc
        if entity_id == "sensor.actual_pv":
            return [
                {"time": "2026-04-03T09:00:00+02:00", "value": 1000.0, "unit": "W"},
                {"time": "2026-04-03T10:00:00+02:00", "value": 2000.0, "unit": "W"},
                {"time": "2026-04-04T09:00:00+02:00", "value": 1500.0, "unit": "W"},
            ]
        if entity_id == "sensor.forecast_today":
            return [
                {"time": "2026-04-03T18:00:00+02:00", "value": 12.0, "unit": "kWh"},
                {"time": "2026-04-04T18:00:00+02:00", "value": 13.0, "unit": "kWh"},
            ]
        if entity_id == "sensor.forecast_tomorrow":
            return [
                {"time": "2026-04-02T20:00:00+02:00", "value": 10.0, "unit": "kWh"},
                {"time": "2026-04-03T20:00:00+02:00", "value": 10.0, "unit": "kWh"},
            ]
        if entity_id == "sensor.forecast_energy_current_hour":
            return [
                {"time": "2026-04-03T09:45:00+02:00", "value": 2.0, "unit": "kWh"},
                {"time": "2026-04-03T10:45:00+02:00", "value": 3.0, "unit": "kWh"},
                {"time": "2026-04-04T09:45:00+02:00", "value": 2.5, "unit": "kWh"},
            ]
        if entity_id == "sensor.forecast_energy_next_hour":
            return [
                {"time": "2026-04-03T08:45:00+02:00", "value": 1.8, "unit": "kWh"},
                {"time": "2026-04-03T09:45:00+02:00", "value": 2.8, "unit": "kWh"},
                {"time": "2026-04-04T08:45:00+02:00", "value": 2.3, "unit": "kWh"},
            ]
        return []

    def aggregate_power_points(points, interval_minutes=15, bucket="day", tzinfo=None):
        assert interval_minutes == 15
        assert bucket == "day"
        assert tzinfo is not None
        assert points
        return {"2026-04-03": 8.0, "2026-04-04": 9.0}

    service = SolarService(
        get_influx_cfg_fn=lambda cfg: {
            "field": "value",
            "measurement": "kWh",
            "interval": "15m",
            "timezone": "Europe/Prague",
            **cfg,
        },
        get_forecast_solar_cfg_fn=lambda cfg: _forecast_cfg(),
        safe_query_entity_last_value_fn=safe_query,
        get_energy_entities_cfg_fn=lambda cfg: {"pv_power_total_entity_id": "sensor.actual_pv"},
        query_entity_series_fn=query_series,
        parse_influx_interval_to_minutes_fn=lambda interval, default_minutes=15: 15,
        aggregate_power_points_fn=aggregate_power_points,
        history_file_path_fn=lambda: history_path,
        now_fn=lambda tzinfo=None: datetime(2026, 4, 5, 12, 0, tzinfo=tzinfo),
        history_backfill_days=3,
    )

    data = service.get_solar_forecast({})

    assert data["history"]["days_tracked"] == 2
    assert data["history"]["hourly_slots_tracked"] >= 3
    assert data["history"]["profile_sources_available"]["historical_hourly"] is True

    saved = json.loads(history_path.read_text(encoding="utf-8"))
    assert saved["2026-04-03"]["actual_total_kwh"] == 8.0
    assert saved["2026-04-03"]["forecast_total_kwh"] == 10.0
    assert saved["2026-04-03"]["forecast_total_source"] == "production_tomorrow_prev_day_last"
    assert saved["2026-04-03"]["forecast_hourly_kwh_by_hour"][9] == 2.0
    assert saved["2026-04-03"]["forecast_hourly_kwh_by_hour"][10] == 3.0
    assert saved["2026-04-03"]["actual_hourly_kwh_by_hour"][9] is not None
