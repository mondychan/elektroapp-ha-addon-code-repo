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
    assert payload["kpi_date"]
    assert len(payload["kpis"]) == 1
    assert payload["kpis"][0]["value"] == pytest.approx(2.0)
    assert payload["kpis"][0]["label"] == "resolved:sensor.hp_power"
    assert payload["kpis"][0]["secondary_metrics"] == [
        {"key": "last", "label": "LAST", "value": 3.0},
        {"key": "min", "label": "MIN", "value": 1.0},
        {"key": "max", "label": "MAX", "value": 3.0},
    ]
    assert len(payload["charts"]) == 1
    assert len(payload["charts"][0]["points"]) >= 3
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
    assert payload["charts"][0]["points"]
    assert all(point["value"] is None for point in payload["charts"][0]["points"])


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
    assert len(payload["charts"][0]["points"]) >= 3


def test_hp_service_fills_missing_day_buckets_with_null_gaps():
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

    def query_series(_influx, _entity_id, start_utc, end_utc, interval, **_kwargs):
        if interval == "15m":
            return [
                {"time": "2026-01-01T00:30:00+00:00", "value": 9.5},
                {"time": "2026-01-01T00:45:00+00:00", "value": 10.0},
            ]
        return []

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value", "measurement": "°C"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 1, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        ),
        query_entity_series=query_series,
        safe_query_entity_last_value=lambda *_args, **_kwargs: {"time": "2026-01-01T00:45:00+00:00", "value": 10.0},
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
                        "entity_id": "sensor.outside_temp",
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

    assert payload["charts"][0]["points"] == [
        {"time": "2026-01-01T00:00:00+00:00", "value": None},
        {"time": "2026-01-01T00:15:00+00:00", "value": None},
        {"time": "2026-01-01T00:30:00+00:00", "value": 9.5},
        {"time": "2026-01-01T00:45:00+00:00", "value": 10.0},
    ]


def test_hp_service_uses_selected_period_for_avg_but_live_value_for_last():
    class StubHaService:
        def resolve_entity_metadata(self, entity_id):
            return {
                "entity_id": entity_id,
                "label": "Outside temperature",
                "unit": "°C",
                "device_class": "temperature",
                "state_class": "measurement",
                "state": "11.0",
                "display_kind": "numeric",
                "source_kind": "instant",
                "kpi_mode": "last",
                "chart_enabled": True,
                "kpi_enabled": True,
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return self.resolve_entity_metadata(entity_id)

    def query_series(_influx, _entity_id, start_utc, end_utc, interval, **_kwargs):
        if interval == "15m":
            return [
                {"time": "2026-01-13T18:00:00+00:00", "value": 14.0},
                {"time": "2026-01-13T19:00:00+00:00", "value": 16.0},
            ]
        if interval == "1h":
            return [
                {"time": "2026-01-07T00:00:00+00:00", "value": 1.0},
                {"time": "2026-01-09T00:00:00+00:00", "value": 2.0},
                {"time": "2026-01-13T00:00:00+00:00", "value": 3.0},
            ]
        return []

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value", "measurement": "°C"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 14, 0, 0, tzinfo=UTC),
        ),
        query_entity_series=query_series,
        safe_query_entity_last_value=lambda *_args, **_kwargs: {"time": "2026-01-13T19:00:00+00:00", "value": 16.0},
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    payload = service.get_data(
        period="week",
        anchor="2026-01-13",
        cfg={
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.outside_temp",
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

    assert payload["kpis"][0]["value"] == pytest.approx(16.0)
    assert payload["kpis"][0]["updated_at"] == "2026-01-13T19:00:00+00:00"
    assert payload["kpis"][0]["secondary_metrics"] == [
        {"key": "avg", "label": "AVG", "value": 2.0},
        {"key": "min", "label": "MIN", "value": 1.0},
        {"key": "max", "label": "MAX", "value": 3.0},
    ]
    assert len(payload["charts"][0]["points"]) == 7
    assert payload["charts"][0]["points"][1]["value"] is None


def test_hp_service_uses_selected_period_values_for_avg_mode():
    class StubHaService:
        def resolve_entity_metadata(self, entity_id):
            return {
                "entity_id": entity_id,
                "label": "Outside temperature",
                "unit": "Â°C",
                "device_class": "temperature",
                "state_class": "measurement",
                "state": "11.0",
                "display_kind": "numeric",
                "source_kind": "instant",
                "kpi_mode": "avg",
                "chart_enabled": True,
                "kpi_enabled": True,
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return self.resolve_entity_metadata(entity_id)

    def query_series(_influx, _entity_id, _start_utc, _end_utc, interval, **_kwargs):
        if interval == "1h":
            return [
                {"time": "2026-01-07T00:00:00+00:00", "value": 1.0},
                {"time": "2026-01-09T00:00:00+00:00", "value": 2.0},
                {"time": "2026-01-13T00:00:00+00:00", "value": 3.0},
            ]
        return []

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value", "measurement": "Â°C"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda date, _start, _end, _tz: (
            datetime(2026, 1, 13, 0, 0, tzinfo=UTC),
            datetime(2026, 1, 14, 0, 0, tzinfo=UTC),
        ),
        query_entity_series=query_series,
        safe_query_entity_last_value=lambda *_args, **_kwargs: {"time": "2026-01-13T19:00:00+00:00", "value": 16.0},
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    payload = service.get_data(
        period="week",
        anchor="2026-01-13",
        cfg={
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.outside_temp",
                        "display_kind": "numeric",
                        "source_kind": "instant",
                        "kpi_enabled": True,
                        "chart_enabled": True,
                        "kpi_mode": "avg",
                    }
                ],
            }
        },
        tzinfo=UTC,
    )

    assert payload["kpis"][0]["value"] == pytest.approx(2.0)
    assert payload["kpis"][0]["secondary_metrics"] == [
        {"key": "last", "label": "LAST", "value": 16.0},
        {"key": "min", "label": "MIN", "value": 1.0},
        {"key": "max", "label": "MAX", "value": 3.0},
    ]


def test_hp_service_merges_scanned_and_manual_entities_with_manual_precedence():
    class StubHaService:
        def get_states(self):
            return [
                {
                    "entity_id": "sensor.hp_scanned",
                    "state": "12.5",
                    "attributes": {
                        "friendly_name": "Scanned sensor",
                        "unit_of_measurement": "°C",
                        "state_class": "measurement",
                    },
                }
            ]

        def resolve_metadata_from_state(self, payload):
            return {
                "entity_id": payload["entity_id"],
                "label": payload["attributes"]["friendly_name"],
                "unit": payload["attributes"]["unit_of_measurement"],
                "device_class": None,
                "state_class": payload["attributes"]["state_class"],
                "state": payload["state"],
                "display_kind": "numeric",
                "source_kind": "instant",
                "kpi_mode": "last",
            }

        def resolve_entity_metadata_safe(self, entity_id):
            return None

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda *_args, **_kwargs: (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)),
        query_entity_series=lambda *_args, **_kwargs: [],
        safe_query_entity_last_value=lambda *_args, **_kwargs: None,
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    resolved = service.resolve_effective_entities(
        {
            "source_mode": "regex",
            "scan": {"regex": "^sensor\\.hp_.*$"},
            "defaults": {"kpi_enabled": True, "chart_enabled_numeric": True, "chart_enabled_state": False, "kpi_mode_numeric": "last", "kpi_mode_state": "last"},
            "overrides": [{"entity_id": "sensor.hp_scanned", "label": "Override label", "chart_enabled": False}],
            "entities": [
                {
                    "entity_id": "sensor.hp_scanned",
                    "label": "Manual label wins",
                    "display_kind": "numeric",
                    "source_kind": "instant",
                    "kpi_enabled": True,
                    "chart_enabled": True,
                    "kpi_mode": "avg",
                    "unit": "°C",
                    "decimals": 1,
                },
                {
                    "entity_id": "sensor.hp_manual_only",
                    "label": "Manual only",
                    "display_kind": "numeric",
                    "source_kind": "instant",
                    "kpi_enabled": True,
                    "chart_enabled": False,
                    "kpi_mode": "last",
                    "unit": "°C",
                },
            ],
        }
    )

    by_id = {entity["entity_id"]: entity for entity in resolved}
    assert set(by_id) == {"sensor.hp_scanned", "sensor.hp_manual_only"}
    assert by_id["sensor.hp_scanned"]["label"] == "Manual label wins"
    assert by_id["sensor.hp_scanned"]["chart_enabled"] is True
    assert by_id["sensor.hp_scanned"]["kpi_mode"] == "avg"
    assert by_id["sensor.hp_manual_only"]["label"] == "Manual only"


def test_hp_service_keeps_manual_entities_when_scan_fails():
    class StubHaService:
        def get_states(self):
            raise RuntimeError("boom")

    service = HPService(
        get_influx_cfg=lambda cfg: {"interval": "15m", "field": "value"},
        get_hp_cfg=lambda cfg: cfg["hp"],
        parse_time_range=lambda *_args, **_kwargs: (datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC)),
        query_entity_series=lambda *_args, **_kwargs: [],
        safe_query_entity_last_value=lambda *_args, **_kwargs: None,
        home_assistant_service=StubHaService(),
        logger=logging.getLogger("test.hp"),
    )

    resolved = service.resolve_effective_entities(
        {
            "source_mode": "prefix",
            "scan": {"prefix": "sensor.hp_"},
            "entities": [
                {
                    "entity_id": "sensor.hp_manual_only",
                    "label": "Manual only",
                    "display_kind": "numeric",
                    "source_kind": "instant",
                    "kpi_enabled": True,
                    "chart_enabled": False,
                    "kpi_mode": "last",
                }
            ],
            "overrides": [],
        }
    )

    assert resolved == [
        {
            "entity_id": "sensor.hp_manual_only",
            "label": "Manual only",
            "display_kind": "numeric",
            "source_kind": "instant",
            "kpi_enabled": True,
            "chart_enabled": False,
            "kpi_mode": "last",
        }
    ]
