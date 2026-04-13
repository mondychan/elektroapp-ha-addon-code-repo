import logging
from datetime import UTC, datetime

import pytest

from fastapi import HTTPException

from services.home_assistant_service import HomeAssistantService
from services.hp_service import HPService


class StubResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise HTTPException(status_code=self.status_code, detail="request failed")

    def json(self):
        return self._payload


def test_home_assistant_service_resolves_numeric_metadata(monkeypatch):
    service = HomeAssistantService(logger=logging.getLogger("test.hp"), base_url="http://example")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "token")
    service.session.get = lambda *args, **kwargs: StubResponse(
        200,
        {
            "state": "1.82",
            "attributes": {
                "friendly_name": "Yield",
                "unit_of_measurement": "kW",
                "device_class": "power",
                "state_class": "measurement",
            },
        },
    )

    resolved = service.resolve_entity_metadata("sensor.ebusd_ha_daemon_hmu_currentyieldpower")

    assert resolved["label"] == "Yield"
    assert resolved["display_kind"] == "numeric"
    assert resolved["source_kind"] == "instant"
    assert resolved["kpi_mode"] == "last"
    assert resolved["unit"] == "kW"


def test_hp_service_returns_numeric_kpis_status_cards_and_charts():
    class StubHaService:
        def resolve_entity_metadata(self, entity_id):
            return {
                "entity_id": entity_id,
                "label": f"resolved:{entity_id}",
                "unit": "kW" if entity_id == "sensor.hp_power" else None,
                "device_class": "power" if entity_id == "sensor.hp_power" else None,
                "state_class": "measurement" if entity_id == "sensor.hp_power" else None,
                "state": "on" if entity_id == "binary_sensor.hp_mode" else "1.0",
                "display_kind": "numeric" if entity_id == "sensor.hp_power" else "state",
                "source_kind": "instant" if entity_id == "sensor.hp_power" else "state",
                "kpi_mode": "last",
                "chart_enabled": entity_id == "sensor.hp_power",
                "kpi_enabled": True,
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return self.resolve_entity_metadata(entity_id)

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        ),
        query_entity_series=lambda _influx, entity_id, *_args, **_kwargs: (
            [
                {"time": "2026-01-01T00:00:00+00:00", "value": 1.0},
                {"time": "2026-01-01T00:15:00+00:00", "value": 2.0},
                {"time": "2026-01-01T00:30:00+00:00", "value": 3.0},
            ]
            if entity_id == "sensor.hp_power"
            else []
        ),
        safe_query_entity_last_value=lambda _influx, entity_id, **_kwargs: (
            {"time": "2026-01-01T00:30:00+00:00", "value": 3.0, "raw_value": 3.0}
            if entity_id == "sensor.hp_power"
            else {"time": "2026-01-01T00:30:00+00:00", "value": "on", "raw_value": "on"}
        ),
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    payload = service.get_data(
        period="day",
        anchor="2026-01-01",
        cfg={
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.hp_power",
                        "label": "",
                        "display_kind": "numeric",
                        "source_kind": "instant",
                        "kpi_enabled": True,
                        "chart_enabled": True,
                        "kpi_mode": "avg",
                        "unit": "",
                    },
                    {
                        "entity_id": "binary_sensor.hp_mode",
                        "label": "",
                        "display_kind": "state",
                        "source_kind": "state",
                        "kpi_enabled": True,
                        "chart_enabled": False,
                        "kpi_mode": "last",
                        "unit": None,
                    },
                ],
            }
        },
        tzinfo=UTC,
    )

    assert payload["date"] == "2026-01-01"
    assert payload["period"] == "day"
    assert payload["anchor"] == "2026-01-01"
    assert len(payload["kpis"]) == 1
    assert payload["kpis"][0]["value"] == pytest.approx(2.0)
    assert payload["kpis"][0]["label"] == "resolved:sensor.hp_power"
    assert payload["kpis"][0]["secondary_metrics"] == [
        {"key": "last", "label": "LAST", "value": 3.0},
        {"key": "min", "label": "MIN", "value": 1.0},
        {"key": "max", "label": "MAX", "value": 3.0},
    ]
    assert len(payload["charts"]) == 1
    assert len(payload["charts"][0]["points"]) == 3
    assert len(payload["status_cards"]) == 1
    assert payload["status_cards"][0]["value"] == "Zapnuto"


def test_hp_service_infers_power_measurements_and_falls_back_to_ha_state():
    captured_measurements = []

    class StubHaService:
        def resolve_entity_metadata(self, entity_id):
            return {
                "entity_id": entity_id,
                "label": "Power consumption",
                "unit": "kW",
                "device_class": "power",
                "state_class": "measurement",
                "state": "4.25",
                "display_kind": "numeric",
                "source_kind": "instant",
                "kpi_mode": "last",
                "chart_enabled": True,
                "kpi_enabled": True,
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return self.resolve_entity_metadata(entity_id)

    def query_series(_influx, _entity_id, *_args, **kwargs):
        captured_measurements.append(kwargs.get("measurement_candidates"))
        return []

    def query_last(_influx, _entity_id, **kwargs):
        captured_measurements.append(kwargs.get("measurement_candidates"))
        return None

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value", "measurement": "kWh"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        ),
        query_entity_series=query_series,
        safe_query_entity_last_value=query_last,
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    payload = service.get_data(
        period="day",
        anchor="2026-01-01",
        cfg={
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.ebusd_ha_daemon_hmu_powerconsumptionhmu",
                        "label": "",
                        "display_kind": "numeric",
                        "source_kind": "instant",
                        "kpi_enabled": True,
                        "chart_enabled": True,
                        "kpi_mode": "last",
                    }
                ],
            }
        },
        tzinfo=UTC,
    )

    assert captured_measurements
    assert captured_measurements[0] == ["W", "kW"]
    assert payload["kpis"][0]["value"] == pytest.approx(4.25)
    assert payload["kpis"][0]["secondary_metrics"] == []
    assert payload["charts"][0]["points"] == []


def test_hp_service_preserves_celsius_measurement_case_for_series():
    captured_measurements = []
    captured_aggregate_fns = []

    class StubHaService:
        def resolve_entity_metadata(self, entity_id):
            return {
                "entity_id": entity_id,
                "label": "Outside temperature",
                "unit": "°C",
                "device_class": "temperature",
                "state_class": "measurement",
                "state": "10.0",
                "display_kind": "numeric",
                "source_kind": "instant",
                "kpi_mode": "last",
                "chart_enabled": True,
                "kpi_enabled": True,
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return self.resolve_entity_metadata(entity_id)

    def query_series(_influx, _entity_id, *_args, **kwargs):
        captured_measurements.append(kwargs.get("measurement_candidates"))
        captured_aggregate_fns.append(kwargs.get("aggregate_fn"))
        return [
            {"time": "2026-01-01T00:00:00+00:00", "value": 9.5},
            {"time": "2026-01-01T00:15:00+00:00", "value": 10.0},
            {"time": "2026-01-01T00:30:00+00:00", "value": 10.5},
        ]

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value", "measurement": "kWh"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
        ),
        query_entity_series=query_series,
        safe_query_entity_last_value=lambda *_args, **_kwargs: None,
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    payload = service.get_data(
        period="day",
        anchor="2026-01-01",
        cfg={
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.ebusd_ha_daemon_broadcast_outsidetemp",
                        "display_kind": "numeric",
                        "source_kind": "instant",
                        "kpi_enabled": True,
                        "chart_enabled": True,
                        "kpi_mode": "last",
                    }
                ],
            }
        },
        tzinfo=UTC,
    )

    assert captured_measurements[0] == ["°C", "°c"]
    assert captured_aggregate_fns[0] == "mean"
    assert payload["kpis"][0]["secondary_metrics"] == [
        {"key": "avg", "label": "AVG", "value": 10.0},
        {"key": "min", "label": "MIN", "value": 9.5},
        {"key": "max", "label": "MAX", "value": 10.5},
    ]
    assert len(payload["charts"][0]["points"]) == 3
