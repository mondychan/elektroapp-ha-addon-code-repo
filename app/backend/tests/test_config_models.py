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
