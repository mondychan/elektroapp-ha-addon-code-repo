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
