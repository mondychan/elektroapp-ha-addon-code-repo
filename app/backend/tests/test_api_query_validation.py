import logging
from zoneinfo import ZoneInfo

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dependencies import RequestContext, get_request_context
from errors import register_error_handling
from routers.api_router import router as api_router


def build_test_app():
    app = FastAPI()
    register_error_handling(app, logging.getLogger("test.validation"))
    app.include_router(api_router)
    app.dependency_overrides[get_request_context] = lambda: RequestContext(
        config={"influxdb": {"timezone": "Europe/Prague"}},
        tzinfo=ZoneInfo("Europe/Prague"),
    )
    return app


def test_costs_rejects_invalid_date_query():
    client = TestClient(build_test_app())
    resp = client.get("/api/costs", params={"date": "2026-99-99"})

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"


def test_consumption_requires_start_and_end_together():
    client = TestClient(build_test_app())
    resp = client.get("/api/consumption", params={"start": "2026-02-20T00:00:00+01:00"})

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"


def test_history_heatmap_rejects_unknown_metric():
    client = TestClient(build_test_app())
    resp = client.get("/api/history-heatmap", params={"month": "2026-02", "metric": "unknown"})

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"


def test_energy_balance_rejects_invalid_period():
    client = TestClient(build_test_app())
    resp = client.get("/api/energy-balance", params={"period": "daily"})

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"


def test_energy_balance_accepts_month_anchor(monkeypatch):
    monkeypatch.setattr("app_service.get_energy_balance", lambda **kwargs: {"ok": True})
    client = TestClient(build_test_app())
    resp = client.get("/api/energy-balance", params={"period": "month", "anchor": "2026-03"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_energy_balance_accepts_year_anchor(monkeypatch):
    monkeypatch.setattr("app_service.get_energy_balance", lambda **kwargs: {"ok": True})
    client = TestClient(build_test_app())
    resp = client.get("/api/energy-balance", params={"period": "year", "anchor": "2026"})

    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_energy_balance_rejects_invalid_month_anchor():
    client = TestClient(build_test_app())
    resp = client.get("/api/energy-balance", params={"period": "month", "anchor": "2026-13"})

    assert resp.status_code == 422
    payload = resp.json()["error"]
    assert payload["code"] == "VALIDATION_ERROR"
