from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from services import pnd_service as pnd_module
from services.pnd_service import (
    HttpSessionPNDPortalClient,
    PNDExportBundle,
    PNDService,
    PNDServiceError,
    normalize_pnd_interval_exports,
    should_run_pnd_window,
)


CONSUMPTION_CSV = """Datum;Spotreba
04.04.2026 00:15:00;0,10
04.04.2026 00:30:00;0,20
05.04.2026 00:00:00;0,30
"""

PRODUCTION_CSV = """Datum;Vyroba
04.04.2026 00:15:00;0,01
04.04.2026 00:30:00;0,02
05.04.2026 00:00:00;0,03
"""

VALID_JSON_PAYLOAD = {
    "series": [
        {
            "name": "+A spotreba",
            "data": [
                ["04.04.2026 00:15:00", 0.1],
                ["04.04.2026 00:30:00", 0.2],
            ],
        },
        {
            "name": "-A vyroba",
            "data": [
                ["04.04.2026 00:15:00", 0.01],
                ["04.04.2026 00:30:00", 0.02],
            ],
        },
    ]
}


class BundleClient:
    def __init__(self, json_payload=None):
        self.json_payload = VALID_JSON_PAYLOAD if json_payload is None else json_payload

    def verify(self, pnd_cfg, probe_date):
        return {
            "ok": True,
            "message": "verify ok",
            "details": {
                "portal_version": "1.2.3",
                "meter_id": pnd_cfg["meter_id"],
                "probe_date": probe_date.isoformat(),
                "recognized_series": ["+a spotreba", "-a vyroba"],
                "unknown_series": [],
                "interval_count": 2,
            },
        }

    def fetch_range(self, pnd_cfg, start_date, end_date):
        return PNDExportBundle(
            json_data=self.json_payload,
            portal_version="1.2.3",
            raw_metadata={"start": start_date.isoformat(), "end": end_date.isoformat(), "meter_id": pnd_cfg["meter_id"]},
        )


def build_service(tmp_path: Path, *, client_factory=None):
    return PNDService(
        tmp_path / "pnd-cache",
        client_factory=client_factory or (lambda: BundleClient()),
        now_fn=lambda: "2026-04-05T10:00:00Z",
    )


class StubResponse:
    def __init__(self, *, text="", status_code=200, json_data=None, url=None):
        self.text = text
        self.status_code = status_code
        self._json_data = json_data
        self.url = url or pnd_module.PND_DASHBOARD_URL

    def json(self):
        return self._json_data


class StubHttpxClient:
    def __init__(self, events):
        self.events = list(events)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        event = self.events.pop(0)
        if isinstance(event, Exception):
            raise event
        return event

    def close(self):
        return None


def test_normalize_pnd_interval_exports_builds_daily_payload():
    normalized = normalize_pnd_interval_exports(
        CONSUMPTION_CSV,
        PRODUCTION_CSV,
        fetched_at="2026-04-05T10:00:00Z",
        raw_refs={"consumption_csv": "a.csv", "production_csv": "b.csv"},
        portal_version="1.2.3",
    )

    assert list(normalized) == ["2026-04-04"]
    day = normalized["2026-04-04"]
    assert len(day["intervals"]) == 3
    assert day["totals"]["consumption_kwh"] == 0.6
    assert day["totals"]["production_kwh"] == 0.06


def test_http_adapter_verify_checks_dashboard_and_data_contract(monkeypatch):
    stub = StubHttpxClient(
        [
            StubResponse(text='<input type="hidden" name="execution" value="token-123">'),
            StubResponse(text="Naměřená data"),
            StubResponse(text="Naměřená data<div>Verze aplikace: 1.2.3</div>"),
            StubResponse(text='{"series":[]}', json_data=VALID_JSON_PAYLOAD),
        ]
    )
    monkeypatch.setattr(pnd_module.httpx, "Client", lambda **kwargs: stub)

    client = HttpSessionPNDPortalClient()
    result = client.verify(
        {"enabled": True, "username": "user", "password": "pass", "meter_id": "3000012345"},
        date(2026, 4, 4),
    )

    assert result["ok"] is True
    assert result["details"]["portal_version"] == "1.2.3"
    assert result["details"]["meter_id"] == "3000012345"
    assert result["details"]["recognized_series"] == ["+a spotreba", "-a vyroba"]
    assert stub.calls[-1][1] == pnd_module.PND_DATA_ENDPOINT
    assert stub.calls[-1][2]["json"]["electrometerId"] == "3000012345"


def test_http_adapter_maps_timeout_to_pnd_service_error(monkeypatch):
    stub = StubHttpxClient(
        [
            StubResponse(text='<input type="hidden" name="execution" value="token-123">'),
            StubResponse(text="Naměřená data"),
            httpx.ReadTimeout("timed out"),
        ]
    )
    monkeypatch.setattr(pnd_module.httpx, "Client", lambda **kwargs: stub)

    client = HttpSessionPNDPortalClient()
    with pytest.raises(PNDServiceError) as exc_info:
        client.fetch_range(
            {"enabled": True, "username": "user", "password": "pass", "meter_id": "3000012345"},
            date(2026, 4, 4),
            date(2026, 4, 4),
        )

    assert exc_info.value.code == "PND_NETWORK_TIMEOUT"
    assert exc_info.value.stage == "fetch"


def test_pnd_service_verify_fetch_and_query_data(tmp_path):
    service = build_service(tmp_path)
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    verify = service.verify(cfg)
    assert verify["ok"] is True
    assert verify["details"]["meter_id"] == "3000012345"

    fetched = service.fetch_day(cfg, datetime(2026, 4, 4).date(), reason="manual")
    assert fetched["saved_days"] == 1

    status = service.get_status(pnd_cfg=cfg)
    assert status["healthy"] is True
    assert status["portal_version"] == "1.2.3"
    assert status["cached_from"] == "2026-04-04"
    assert status["cached_to"] == "2026-04-04"
    assert status["state"] == "cache_ready"

    data = service.get_data("2026-04-04", "2026-04-04")
    assert data["days_count"] == 1
    assert data["days"][0]["totals"]["consumption_kwh"] == 0.3


def test_pnd_service_fails_on_empty_payload(tmp_path):
    service = build_service(tmp_path, client_factory=lambda: BundleClient(json_payload={"series": []}))
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    with pytest.raises(PNDServiceError) as exc_info:
        service.fetch_day(cfg, date(2026, 4, 4), reason="manual")

    assert exc_info.value.code == "PND_DATA_NOT_AVAILABLE"


def test_pnd_service_fails_on_unknown_payload_series(tmp_path):
    payload = {"series": [{"name": "mystery-series", "data": [["04.04.2026 00:15:00", 1.0]]}]}
    service = build_service(tmp_path, client_factory=lambda: BundleClient(json_payload=payload))
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    with pytest.raises(PNDServiceError) as exc_info:
        service.fetch_day(cfg, date(2026, 4, 4), reason="manual")

    assert exc_info.value.code == "PND_PORTAL_CHANGED"
    assert "mystery-series" in exc_info.value.details["series_names"]


def test_pnd_service_requires_enabled_and_credentials(tmp_path):
    service = build_service(tmp_path)
    with pytest.raises(PNDServiceError) as exc_info:
        service.verify({"enabled": False, "username": "", "password": "", "meter_id": ""})

    assert exc_info.value.code == "PND_DISABLED"


def test_should_run_pnd_window_accepts_night_retry_window():
    assert should_run_pnd_window(datetime(2026, 4, 5, 2, 0, 0)) is True
    assert should_run_pnd_window(datetime(2026, 4, 5, 7, 59, 0)) is True
    assert should_run_pnd_window(datetime(2026, 4, 5, 1, 59, 0)) is False
    assert should_run_pnd_window(datetime(2026, 4, 5, 8, 0, 0)) is False
    assert should_run_pnd_window(datetime(2026, 4, 5, 4, 30, 0), start_hour=4, end_hour=5) is True
