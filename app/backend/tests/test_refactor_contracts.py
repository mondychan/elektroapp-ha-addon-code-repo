import asyncio
import json
import logging
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from container import ApplicationContainer, build_container
from dependencies import RequestContext, get_request_context
from errors import register_error_handling
from influx import (
    build_influx_from_clause,
    escape_influx_tag_value,
    quote_influx_identifier,
    validate_influx_aggregate,
    validate_influx_interval,
)
from routers.api_router import router as api_router
from services.cache_manager import SeriesCache
from services.recommendation_service import RecommendationService


def build_test_app():
    app = FastAPI()
    register_error_handling(app, logging.getLogger("test.refactor_contracts"))
    app.include_router(api_router)
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        config={"influxdb": {"timezone": "Europe/Prague"}},
        tzinfo=ZoneInfo("Europe/Prague"),
    )
    return app


def test_application_container_wires_runtime_paths_and_security_flags(monkeypatch, tmp_path):
    monkeypatch.setenv("ELEKTROAPP_STORAGE", str(tmp_path))
    monkeypatch.setenv("ELEKTROAPP_CORS_ORIGINS", "https://example.test, https://ha.test")
    monkeypatch.setenv("ELEKTROAPP_API_TOKEN", "secret")

    container = build_container()

    assert isinstance(container, ApplicationContainer)
    assert container.config.storage_dir == tmp_path
    assert container.config.cache_dir == tmp_path / "prices-cache"
    assert container.application is not None
    assert container.cors_origins == ["https://example.test", "https://ha.test"]
    assert container.api_token_configured is True
    assert container.runtime_state is not None


def test_mutation_guard_rejects_cross_origin_and_accepts_token(monkeypatch):
    import app_service

    monkeypatch.setenv("ELEKTROAPP_API_TOKEN", "secret")
    monkeypatch.setattr(app_service, "invalidate_cache", lambda domain, date=None: {"ok": True, "domain": domain, "date": date})
    client = TestClient(build_test_app())

    denied = client.post("/api/cache/invalidate", json={"domain": "prices"}, headers={"Origin": "https://evil.test"})
    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "mutation_forbidden"

    accepted = client.post(
        "/api/cache/invalidate",
        json={"domain": "prices", "date": "2026-04-23"},
        headers={"Origin": "https://evil.test", "X-Elektroapp-Token": "secret"},
    )
    assert accepted.status_code == 200
    assert accepted.json() == {"ok": True, "domain": "prices", "date": "2026-04-23"}


def test_typed_payload_validation_rejects_bad_cache_domain():
    client = TestClient(build_test_app())

    resp = client.post("/api/cache/invalidate", json={"domain": "unknown"})

    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_influx_query_helpers_escape_identifiers_tags_and_validate_controls():
    influx_cfg = {
        "retention_policy": 'autogen"rp',
        "measurement": 'kWh"house',
    }

    assert build_influx_from_clause(influx_cfg) == '"autogen\\"rp"."kWh\\"house"'
    assert quote_influx_identifier('field"name') == '"field\\"name"'
    assert escape_influx_tag_value("sensor.grid'import\\main") == "sensor.grid\\'import\\\\main"
    assert validate_influx_interval("15m") == "15m"
    assert validate_influx_interval("15m; drop measurement") == "15m"
    assert validate_influx_aggregate("mean") == "mean"
    assert validate_influx_aggregate("mean(value)") == "last"


def test_series_cache_save_uses_atomic_file_and_metadata_contract(tmp_path):
    cache = SeriesCache("consumption", tmp_path, ttl_seconds=60)

    cache.save("2026-04-23", {"entity_id": "sensor.main"}, {"points": [1]}, source="influx", status="partial")

    path = tmp_path / "consumption-2026-04-23.json"
    assert path.exists()
    assert not (tmp_path / "consumption-2026-04-23.json.tmp").exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["meta"]["cache_version"] == 2
    assert payload["meta"]["key"] == {"entity_id": "sensor.main"}
    assert payload["meta"]["source"] == "influx"
    assert payload["meta"]["status"] == "partial"
    assert payload["meta"]["fetched_at"]
    assert payload["meta"]["complete_after"]


def test_cache_invalidation_removes_selected_domain_date(backend_main, isolated_storage):
    target = isolated_storage["consumption_cache_dir"] / "consumption-2026-04-23.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("{}", encoding="utf-8")

    result = backend_main.invalidate_cache(domain="consumption", date="2026-04-23")

    assert result["ok"] is True
    assert result["domain"] == "consumption"
    assert not target.exists()
    assert str(target) in result["removed"]


def test_recommendation_service_builds_actionable_payload():
    service = RecommendationService()

    result = service.build(
        date="2026-04-23",
        prices=[
            {"time": "2026-04-23 03:00", "final": 1.0},
            {"time": "2026-04-23 18:00", "final": 3.0},
        ],
        schedule={"recommendations": [{"start": "2026-04-23 03:00", "end": "2026-04-23 05:00", "avg_price": 1.2}]},
        battery={"status": {"soc_percent": 20}},
        solar={"enabled": True, "comparison": {"adjusted_projection_tomorrow_kwh": 9.5}},
        costs={"summary": {"cost_total": 10}},
        export={"summary": {"sell_total": 2}},
    )

    action_types = {item["type"] for item in result["actions"]}
    metric_keys = {item["key"] for item in result["metrics"]}
    assert result["date"] == "2026-04-23"
    assert {"run_load", "save_battery", "charge_battery", "defer_load"}.issubset(action_types)
    assert {"avg_price", "battery_soc", "solar_tomorrow", "net_today"}.issubset(metric_keys)
    assert 0 < result["confidence"] <= 1


def test_dashboard_snapshot_keeps_legacy_and_new_contract_keys(monkeypatch, backend_main):
    tzinfo = ZoneInfo("Europe/Prague")

    monkeypatch.setattr(backend_main, "get_prices", lambda date=None, cfg=None, tzinfo=None: {"prices": [{"date": date, "final": 1.0}]})
    monkeypatch.setattr(backend_main, "get_costs", lambda *args, **kwargs: {"points": [], "summary": {"cost_total": 1}})
    monkeypatch.setattr(backend_main, "get_export", lambda *args, **kwargs: {"points": [], "summary": {"sell_total": 0}})
    monkeypatch.setattr(backend_main, "get_battery", lambda *args, **kwargs: {"enabled": False})
    monkeypatch.setattr(backend_main, "get_alerts", lambda *args, **kwargs: [])
    monkeypatch.setattr(backend_main, "get_comparison", lambda *args, **kwargs: {"ok": True})
    monkeypatch.setattr(backend_main, "get_solar_forecast", lambda *args, **kwargs: None)
    monkeypatch.setattr(backend_main, "get_recommendations", lambda *args, **kwargs: {"actions": [], "metrics": []})
    monkeypatch.setattr(backend_main, "get_diagnostics", lambda *args, **kwargs: {"cache": {}, "runtime": {}})

    snapshot = asyncio.run(backend_main.get_dashboard_snapshot(date="2026-04-23", cfg={}, tzinfo=tzinfo))

    assert snapshot["prices"] == {"prices": [{"date": "2026-04-23", "final": 1.0}]}
    assert snapshot["selected_date_prices"] == [{"date": "2026-04-23", "final": 1.0}]
    assert "today_prices" in snapshot
    assert "tomorrow_prices" in snapshot
    assert snapshot["recommendations"] == {"actions": [], "metrics": []}
    assert snapshot["diagnostics_summary"] == {"cache": {}, "runtime": {}}
