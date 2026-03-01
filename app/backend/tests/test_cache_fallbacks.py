import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import HTTPException


def _base_influx_cfg():
    return {
        "host": "localhost",
        "port": 8086,
        "database": "homeassistant",
        "measurement": "kWh",
        "field": "value",
        "entity_id": "sensor.import",
        "retention_policy": "autogen",
        "timezone": "Europe/Prague",
        "interval": "15m",
    }


def test_consumption_returns_stale_cache_as_fallback_on_query_error(monkeypatch, backend_main, isolated_storage):
    tzinfo = ZoneInfo("Europe/Prague")
    today = datetime.now(tzinfo).strftime("%Y-%m-%d")
    cache_key = backend_main.build_consumption_cache_key(_base_influx_cfg())
    cache_path = isolated_storage["consumption_cache_dir"] / f"consumption-{today}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{}", encoding="utf-8")
    stale_mtime = time.time() - (backend_main.CONSUMPTION_CACHE_TTL_SECONDS + 10)
    os.utime(cache_path, (stale_mtime, stale_mtime))

    cached_payload = {
        "range": {"start": "2026-02-20T00:00:00Z", "end": "2026-02-21T00:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.import",
        "points": [{"time": "2026-02-20T00:00:00+01:00", "time_utc": "2026-02-19T23:00:00Z", "kwh": 0.5}],
        "has_series": True,
    }

    monkeypatch.setattr(
        backend_main,
        "load_consumption_cache",
        lambda date_str, key: (cached_payload.copy(), cache_path, {"key": cache_key, "fetched_at": "2026-02-20T00:00:00Z"}),
    )
    monkeypatch.setattr(
        backend_main,
        "influx_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=500, detail="boom")),
    )

    cfg = {"influxdb": _base_influx_cfg()}
    result = backend_main.get_consumption_points(cfg, date=today)

    assert result["from_cache"] is True
    assert result["cache_fallback"] is True
    assert result["points"] == cached_payload["points"]


def test_export_returns_stale_cache_as_fallback_on_query_error(monkeypatch, backend_main, isolated_storage):
    tzinfo = ZoneInfo("Europe/Prague")
    today = datetime.now(tzinfo).strftime("%Y-%m-%d")
    influx_cfg = _base_influx_cfg()
    influx_cfg["export_entity_id"] = "sensor.export"
    cache_key = backend_main.build_export_cache_key(influx_cfg, "sensor.export")
    cache_path = isolated_storage["export_cache_dir"] / f"export-{today}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{}", encoding="utf-8")
    stale_mtime = time.time() - (backend_main.EXPORT_CACHE_TTL_SECONDS + 10)
    os.utime(cache_path, (stale_mtime, stale_mtime))

    cached_payload = {
        "range": {"start": "2026-02-20T00:00:00Z", "end": "2026-02-21T00:00:00Z"},
        "interval": "15m",
        "entity_id": "sensor.export",
        "points": [{"time": "2026-02-20T00:00:00+01:00", "time_utc": "2026-02-19T23:00:00Z", "kwh": 0.2}],
        "has_series": True,
    }

    monkeypatch.setattr(
        backend_main,
        "load_export_cache",
        lambda date_str, key: (cached_payload.copy(), cache_path, {"key": cache_key, "fetched_at": "2026-02-20T00:00:00Z"}),
    )
    monkeypatch.setattr(
        backend_main,
        "influx_query",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(HTTPException(status_code=500, detail="boom")),
    )

    cfg = {"influxdb": influx_cfg}
    result = backend_main.get_export_points(cfg, date=today)

    assert result["from_cache"] is True
    assert result["cache_fallback"] is True
    assert result["points"] == cached_payload["points"]
