import logging

from services.influx_service import InfluxService


INFLUX = {"host": "influx", "port": 8086, "database": "homeassistant", "field": "value", "measurement": "kWh"}


def make_service(rows_by_measurement):
    """Fake InfluxService whose HTTP layer is a dict measurement -> rows."""
    service = InfluxService(logger=logging.getLogger("test"))
    calls = []

    def fake_query(influx, query):
        calls.append(query)
        for measurement, rows in rows_by_measurement.items():
            if '"%s"' % measurement in query and "FROM" in query:
                return {"results": [{"series": [{"tags": {"entity_id": entity}, "values": values} for entity, values in rows]}]}
        return {"results": [{}]}

    service.influx_query = fake_query  # type: ignore[assignment]
    return service, calls


def test_batch_query_groups_by_measurement_and_maps_keys():
    service, calls = make_service(
        {
            "kWh": [("sensor.pv_today", [[1000, 12.5]])],
            "%": [("sensor.soc", [[1000, 76]])],
        }
    )

    out = service.query_entity_last_values(
        INFLUX,
        {
            "pv": {"entity_id": "sensor.pv_today", "measurements": ["kWh"]},
            "soc": {"entity_id": "sensor.soc", "measurements": ["%"]},
            "missing": {"entity_id": ""},
        },
        tzinfo=None,
    )

    assert set(out) == {"pv", "soc"}
    assert out["pv"]["value"] == 12.5
    assert out["pv"]["unit"] == "kWh"
    assert out["soc"]["value"] == 76.0
    assert out["soc"]["unit"] == "%"
    # one request per measurement bucket, never one per entity
    assert len(calls) == 2
    assert all('GROUP BY "entity_id"' in q for q in calls)


def test_batch_query_merges_same_measurement_entities_into_one_request():
    service, calls = make_service(
        {
            "W": [
                ("sensor.a", [[1000, 300]]),
                ("sensor.b", [[1000, 120]]),
            ]
        }
    )

    out = service.query_entity_last_values(
        INFLUX,
        {
            "a": {"entity_id": "sensor.a", "measurements": ["W"]},
            "b": {"entity_id": "sensor.b", "measurements": ["W"]},
        },
    )

    assert len(calls) == 1
    assert "sensor.a" in calls[0] and "sensor.b" in calls[0]
    assert out["a"]["value"] == 300.0
    assert out["b"]["value"] == 120.0


def test_batch_query_falls_back_to_suffix_spelling():
    service, _ = make_service({"W": [("a", [[1000, 42]])]})

    out = service.query_entity_last_values(
        INFLUX,
        {"a": {"entity_id": "sensor.a", "measurements": ["W"]}},
    )

    assert out["a"]["value"] == 42.0


def test_batch_query_tolerates_missing_and_broken_entities():
    import requests

    service = InfluxService(logger=logging.getLogger("test"))
    service.influx_query = lambda influx, query: (_ for _ in ()).throw(requests.RequestException("boom"))  # type: ignore

    out = service.safe_query_entity_last_values(
        INFLUX,
        {
            "ok": {"entity_id": "sensor.ok", "measurements": ["W"]},
            "empty": {"entity_id": "", "measurements": ["W"]},
        },
    )

    assert out == {"ok": None, "empty": None}
