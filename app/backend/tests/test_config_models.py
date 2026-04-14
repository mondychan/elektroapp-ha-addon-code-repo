import pytest
from pydantic import ValidationError

from config_models import AppConfigModel


def test_config_model_normalizes_provider_dph_and_applies_defaults():
    model = AppConfigModel.model_validate(
        {
            "dph": 1.21,
            "price_provider": "ote-cr.cz",
            "influxdb": {
                "host": "127.0.0.1",
                "database": "ha",
                "measurement": "kWh",
                "field": "value",
                "entity_id": "sensor.import",
            },
        }
    )
    dumped = model.model_dump()

    assert dumped["dph"] == pytest.approx(21.0)
    assert dumped["price_provider"] == "ote"
    assert dumped["influxdb"]["port"] == 8086
    assert dumped["poplatky"]["oze"] == 0.0
    assert dumped["battery"]["reserve_soc_percent"] == 15.0
    assert dumped["pnd"]["nightly_sync_enabled"] is True
    assert dumped["hp"]["entities"] == []


def test_config_model_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        AppConfigModel.model_validate({"unknown": 123})

    with pytest.raises(ValidationError):
        AppConfigModel.model_validate(
            {
                "influxdb": {
                    "host": "127.0.0.1",
                    "database": "ha",
                    "measurement": "kWh",
                    "field": "value",
                    "entity_id": "sensor.import",
                    "unexpected": "nope",
                }
            }
        )


def test_tarif_periods_accept_string_and_validate_range():
    model = AppConfigModel.model_validate({"tarif": {"vt_periods": "6-7, 9-10"}})
    assert model.tarif.vt_periods == [(6, 7), (9, 10)]

    with pytest.raises(ValidationError):
        AppConfigModel.model_validate({"tarif": {"vt_periods": [[25, 26]]}})


def test_poplatky_oze_accepts_legacy_poze_alias():
    model = AppConfigModel.model_validate({"poplatky": {"poze": 0.123}})
    assert model.poplatky.oze == pytest.approx(0.123)


def test_pnd_config_accepts_credentials_and_defaults():
    model = AppConfigModel.model_validate(
        {
            "pnd": {
                "enabled": True,
                "username": "user@example.com",
                "password": "secret",
                "meter_id": "3000012345",
            }
        }
    )

    assert model.pnd.enabled is True
    assert model.pnd.verify_on_startup is True
    assert model.pnd.nightly_sync_enabled is True
    assert model.pnd.nightly_sync_window_start_hour == 2
    assert model.pnd.nightly_sync_window_end_hour == 7


def test_pnd_config_rejects_invalid_sync_window():
    with pytest.raises(ValidationError):
        AppConfigModel.model_validate(
            {
                "pnd": {
                    "enabled": True,
                    "username": "user@example.com",
                    "password": "secret",
                    "meter_id": "3000012345",
                    "nightly_sync_window_start_hour": 8,
                    "nightly_sync_window_end_hour": 7,
                }
            }
        )


def test_hp_config_accepts_numeric_and_state_entities():
    model = AppConfigModel.model_validate(
        {
            "hp": {
                "enabled": True,
                "entities": [
                    {
                        "entity_id": "sensor.ebusd_ha_daemon_hmu_currentyieldpower",
                        "label": "Aktualni vykon",
                        "display_kind": "numeric",
                        "source_kind": "instant",
                        "kpi_enabled": True,
                        "chart_enabled": True,
                        "kpi_mode": "avg",
                        "unit": "kW",
                    },
                    {
                        "entity_id": "binary_sensor.ebusd_ha_daemon_hmu_hcmodeactive",
                        "display_kind": "state",
                        "source_kind": "state",
                        "chart_enabled": True,
                        "kpi_mode": "max",
                    },
                ],
            }
        }
    )

    assert model.hp.enabled is True
    assert len(model.hp.entities) == 2
    assert model.hp.entities[0].kpi_mode == "avg"
    assert model.hp.entities[1].chart_enabled is False
    assert model.hp.entities[1].kpi_mode == "last"


def test_hp_config_accepts_duration_value_format_in_overrides():
    model = AppConfigModel.model_validate(
        {
            "hp": {
                "source_mode": "regex",
                "overrides": [
                    {
                        "entity_id": "sensor.ebusd_ha_daemon_global_uptime",
                        "value_format": "duration_seconds",
                        "duration_style": "short",
                        "duration_max_parts": 2,
                    }
                ],
            }
        }
    )

    assert model.hp.overrides[0].value_format == "duration_seconds"
    assert model.hp.overrides[0].duration_style == "short"
    assert model.hp.overrides[0].duration_max_parts == 2


def test_hp_config_rejects_invalid_mode_for_instant_entity():
    with pytest.raises(ValidationError):
        AppConfigModel.model_validate(
            {
                "hp": {
                    "entities": [
                        {
                            "entity_id": "sensor.test",
                            "display_kind": "numeric",
                            "source_kind": "instant",
                            "kpi_mode": "delta",
                        }
                    ]
                }
            }
        )
