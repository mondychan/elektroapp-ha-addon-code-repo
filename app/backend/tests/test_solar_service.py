import json

from datetime import datetime

from services.solar_service import SolarService


def test_solar_service_uses_measurement_candidates_by_metric(tmp_path):
    calls = []

    def safe_query(_influx, entity_id, **kwargs):
        calls.append((entity_id, kwargs))
        if kwargs.get("numeric", True):
            return {"value": 1.23}
        return {"raw_value": "2026-04-05T12:00:00+02:00"}

    service = SolarService(
        get_influx_cfg_fn=lambda cfg: {"measurement": "kWh", "timezone": "Europe/Prague", **cfg},
        get_forecast_solar_cfg_fn=lambda cfg: {
            "enabled": True,
            "power_now_entity_id": "sensor.power_now",
            "energy_current_hour_entity_id": "sensor.energy_hour",
            "energy_next_hour_entity_id": None,
            "energy_production_today_entity_id": "sensor.energy_today",
            "energy_production_today_remaining_entity_id": None,
            "energy_production_tomorrow_entity_id": None,
            "power_highest_peak_time_today_entity_id": "sensor.peak_today",
            "power_highest_peak_time_tomorrow_entity_id": None,
        },
        safe_query_entity_last_value_fn=safe_query,
        get_energy_entities_cfg_fn=lambda cfg: {"pv_power_total_entity_id": None},
        history_file_path_fn=lambda: tmp_path / "solar-history.json",
        now_fn=lambda tzinfo=None: datetime(2026, 4, 5, 12, 0, tzinfo=tzinfo),
    )

    data = service.get_solar_forecast({})

    assert data["enabled"] is True
    assert data["status"]["power_now"] == 1.23
    assert data["status"]["energy_current_hour"] == 1.23
    assert data["status"]["production_today"] == 1.23
    assert data["status"]["peak_today"] == "2026-04-05T12:00:00+02:00"
    assert data["status"]["peak_time_today_hhmm"] == "12:00"

    by_entity = {entity_id: kwargs for entity_id, kwargs in calls}
    assert by_entity["sensor.power_now"]["measurement_candidates"] == ["W", "kW"]
    assert by_entity["sensor.energy_hour"]["measurement_candidates"] == ["kWh", "Wh"]
    assert by_entity["sensor.energy_today"]["measurement_candidates"] == ["kWh", "Wh"]
    assert by_entity["sensor.peak_today"]["measurement_candidates"] == ["state"]


def test_solar_service_returns_actuals_and_calibrated_projection(tmp_path):
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
            "sensor.forecast_today": {"value": 12.0},
            "sensor.forecast_remaining": {"value": 7.0},
            "sensor.forecast_tomorrow": {"value": 14.0},
            "sensor.actual_pv": {"value": 2200.0},
        }
        return values.get(entity_id)

    def query_series(_influx, entity_id, *_args, **_kwargs):
        assert entity_id == "sensor.actual_pv"
        return [
            {"time": "2026-04-05T09:00:00+02:00", "time_utc": "2026-04-05T07:00:00Z", "value": 2000.0},
            {"time": "2026-04-05T09:15:00+02:00", "time_utc": "2026-04-05T07:15:00Z", "value": 3000.0},
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
        get_forecast_solar_cfg_fn=lambda cfg: {
            "enabled": True,
            "power_now_entity_id": "sensor.forecast_power_now",
            "energy_current_hour_entity_id": None,
            "energy_next_hour_entity_id": None,
            "energy_production_today_entity_id": "sensor.forecast_today",
            "energy_production_today_remaining_entity_id": "sensor.forecast_remaining",
            "energy_production_tomorrow_entity_id": "sensor.forecast_tomorrow",
            "power_highest_peak_time_today_entity_id": None,
            "power_highest_peak_time_tomorrow_entity_id": None,
        },
        safe_query_entity_last_value_fn=safe_query,
        get_energy_entities_cfg_fn=lambda cfg: {"pv_power_total_entity_id": "sensor.actual_pv"},
        query_entity_series_fn=query_series,
        parse_influx_interval_to_minutes_fn=lambda interval, default_minutes=15: 15,
        aggregate_power_points_fn=aggregate_power_points,
        history_file_path_fn=lambda: history_path,
        now_fn=lambda tzinfo=None: datetime(2026, 4, 5, 12, 0, tzinfo=tzinfo),
    )

    data = service.get_solar_forecast({})

    assert data["actual"]["power_now_w"] == 2200.0
    assert data["actual"]["production_today_kwh"] == 5.0
    assert data["comparison"]["forecast_so_far_kwh"] == 5.0
    assert data["comparison"]["delta_so_far_kwh"] == 0.0
    assert data["comparison"]["historical_bias_ratio"] == 0.85
    assert data["comparison"]["live_ratio"] == 1.0
    assert data["comparison"]["effective_bias_ratio"] == 0.91
    assert data["comparison"]["adjusted_projection_today_kwh"] == 11.37
    assert data["comparison"]["projection_delta_to_forecast_kwh"] == -0.63
    assert data["history"]["days_tracked"] == 2

    saved = json.loads(history_path.read_text(encoding="utf-8"))
    assert any(entry.get("actual_total_kwh") == 5.0 for entry in saved.values())
