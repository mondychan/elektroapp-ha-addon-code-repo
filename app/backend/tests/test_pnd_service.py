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
    build_pnd_day_integrity,
    compare_pnd_day_payloads,
    should_run_pnd_window,
)


def _full_day_intervals(day="2026-04-04", consumption=1.0, production=0.5):
    base = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=pnd_module.ZoneInfo("Europe/Prague"))
    return [
        {
            "start": (base + pnd_module.timedelta(minutes=15 * index)).isoformat(),
            "end": (base + pnd_module.timedelta(minutes=15 * (index + 1))).isoformat(),
            "consumption_kwh": consumption / 96,
            "production_kwh": production / 96,
        }
        for index in range(96)
    ]


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

def _full_day_json_series(name, total, day="2026-04-04"):
    base = datetime.strptime(day, "%Y-%m-%d")
    data = []
    for index in range(96):
        if index == 95:
            timestamp = f"{base.strftime('%d.%m.%Y')} 24:00:00"
        else:
            timestamp = (base + pnd_module.timedelta(minutes=15 * (index + 1))).strftime("%d.%m.%Y %H:%M:%S")
        data.append([timestamp, total / 96])
    return {"name": name, "data": data}


VALID_JSON_PAYLOAD = {"series": [_full_day_json_series("+A spotreba", 0.3), _full_day_json_series("-A vyroba", 0.5)]}


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
                "recognized_series": ["+a spotreba (unit: , is_power: False)", "-a vyroba (unit: , is_power: False)"],
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



def test_build_pnd_day_integrity_rejects_missing_direction_slot():
    intervals = _full_day_intervals()
    intervals[-1]["production_kwh"] = None

    result = build_pnd_day_integrity("2026-04-04", intervals)

    assert result["complete"] is False
    assert result["production_kwh"]["missing_count"] == 1
    assert result["consumption_kwh"]["missing_count"] == 0


def test_compare_pnd_day_payloads_reports_value_changes():
    old = {"intervals": _full_day_intervals(consumption=1.0, production=0.5), "totals": {"consumption_kwh": 1.0, "production_kwh": 0.5}}
    new = {"intervals": _full_day_intervals(consumption=1.25, production=0.5), "totals": {"consumption_kwh": 1.25, "production_kwh": 0.5}}

    result = compare_pnd_day_payloads(old, new)

    assert result["changed"] is True
    assert result["reason"] == "interval_values_changed"
    assert result["changed_intervals"] == 96
    assert result["consumption_delta_kwh"] == 0.25

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
    assert result["details"]["recognized_series"] == [
        "+a spotreba (unit: , is_power: False)",
        "-a vyroba (unit: , is_power: False)",
    ]
    assert stub.calls[-1][1] == pnd_module.PND_DATA_ENDPOINT
    assert stub.calls[-1][2]["json"]["electrometerId"] == "3000012345"


def test_http_adapter_accepts_post_login_redirect_without_dashboard_marker(monkeypatch):
    stub = StubHttpxClient(
        [
            StubResponse(text='<input type="hidden" name="execution" value="token-123">'),
            StubResponse(text="<html><body>OAuth redirect in progress</body></html>", url="https://pnd.cezdistribuce.cz/cezpnd2/login/oauth2/code/mepas-external"),
            StubResponse(text="NamÄ›Ĺ™enĂˇ data<div>Verze aplikace: 1.2.3</div>"),
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


def test_http_adapter_returns_login_failed_when_dashboard_still_shows_login_form(monkeypatch):
    login_form_html = '<section id="loginForm"><input name="username"/><input name="password"/><div class="formError">Neplatné přihlašovací údaje</div></section>'
    stub = StubHttpxClient(
        [
            StubResponse(text='<input type="hidden" name="execution" value="token-123">'),
            StubResponse(text="<html><body>OAuth redirect in progress</body></html>", url="https://pnd.cezdistribuce.cz/cezpnd2/login/oauth2/code/mepas-external"),
            StubResponse(text=login_form_html, url="https://cas.cez.cz/cas/login"),
        ]
    )
    monkeypatch.setattr(pnd_module.httpx, "Client", lambda **kwargs: stub)

    client = HttpSessionPNDPortalClient()
    with pytest.raises(PNDServiceError) as exc_info:
        client.verify(
            {"enabled": True, "username": "user", "password": "pass", "meter_id": "3000012345"},
            date(2026, 4, 4),
        )

    assert exc_info.value.code == "PND_LOGIN_FAILED"
    assert exc_info.value.details["portal_message"] == "Neplatné přihlašovací údaje"


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



def test_pnd_service_does_not_overwrite_complete_cache_with_incomplete_response(tmp_path):
    complete_payload = {"series": [_full_day_json_series("+A spotreba", 1.0), _full_day_json_series("-A vyroba", 0.5)]}
    incomplete_payload = {"series": [_full_day_json_series("+A spotreba", 2.0), _full_day_json_series("-A vyroba", 1.0)]}
    incomplete_payload["series"][0]["data"].pop()
    incomplete_payload["series"][1]["data"].pop()
    payloads = iter([complete_payload, incomplete_payload])
    service = build_service(tmp_path, client_factory=lambda: BundleClient(json_payload=next(payloads)))
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    first = service.fetch_day(cfg, date(2026, 4, 4), reason="manual")
    assert first["saved_days"] == 1
    cached_before = service.get_data("2026-04-04", "2026-04-04")["days"][0]

    with pytest.raises(PNDServiceError) as exc_info:
        service.fetch_day(cfg, date(2026, 4, 4), reason="manual")

    assert exc_info.value.code == pnd_module.PND_DATA_INCOMPLETE
    cached_after = service.get_data("2026-04-04", "2026-04-04")["days"][0]
    assert cached_after["totals"] == cached_before["totals"]


def test_pnd_service_rejects_a_missing_requested_day(tmp_path):
    service = build_service(tmp_path)
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    with pytest.raises(PNDServiceError) as exc_info:
        service.fetch_range(cfg, date(2026, 4, 4), date(2026, 4, 5), reason="nightly")

    assert exc_info.value.code == pnd_module.PND_DATA_INCOMPLETE
    assert "2026-04-05" in exc_info.value.details["incomplete_days"]["_missing_days"]["missing"]
    assert service.has_day("2026-04-04") is True
    assert service.has_day("2026-04-05") is False


def test_pnd_service_overwrites_cache_with_corrected_complete_response(tmp_path):
    first_payload = {"series": [_full_day_json_series("+A spotreba", 1.0), _full_day_json_series("-A vyroba", 0.5)]}
    corrected_payload = {"series": [_full_day_json_series("+A spotreba", 2.0), _full_day_json_series("-A vyroba", 1.0)]}
    payloads = iter([first_payload, corrected_payload])
    service = build_service(tmp_path, client_factory=lambda: BundleClient(json_payload=next(payloads)))
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    service.fetch_day(cfg, date(2026, 4, 4), reason="manual")
    service.fetch_day(cfg, date(2026, 4, 4), reason="manual")

    cached = service.get_data("2026-04-04", "2026-04-04")["days"][0]
    assert cached["totals"] == {"consumption_kwh": 2.0, "production_kwh": 1.0}


def test_needs_nightly_sync_requires_a_nightly_job(monkeypatch, tmp_path):
    service = build_service(tmp_path)
    service.find_first_invalid_date = lambda **kwargs: None
    service._save_status(
        {
            "last_sync_at": "2026-04-05T02:10:00Z",
            "last_job": {"type": "sync", "reason": "manual"},
        }
    )
    now = datetime(2026, 4, 5, 3, 0, tzinfo=pnd_module.ZoneInfo("Europe/Prague"))

    assert service.needs_nightly_sync(now=now) is True

    service._save_status(
        {
            "last_sync_at": "2026-04-05T02:10:00Z",
            "last_job": {"type": "sync", "reason": "nightly"},
        }
    )
    assert service.needs_nightly_sync(now=now) is False


def test_run_nightly_sync_revalidates_the_previous_seven_days(monkeypatch, tmp_path):
    requested = []

    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            value = datetime(2026, 4, 5, 3, 0, 0)
            return value.replace(tzinfo=tz)

    class RangeClient:
        def fetch_range(self, pnd_cfg, start_date, end_date):
            requested.append((start_date, end_date))
            consumption = {"name": "+A spotreba", "data": []}
            production = {"name": "-A vyroba", "data": []}
            cursor = start_date
            while cursor <= end_date:
                consumption["data"].extend(_full_day_json_series("+A spotreba", 1.0, cursor.isoformat())["data"])
                production["data"].extend(_full_day_json_series("-A vyroba", 0.5, cursor.isoformat())["data"])
                cursor += pnd_module.timedelta(days=1)
            return PNDExportBundle(json_data={"series": [consumption, production]}, portal_version="1.2.3")

    monkeypatch.setattr(pnd_module, "datetime", FixedDateTime)
    service = build_service(tmp_path, client_factory=lambda: RangeClient())
    service.find_first_invalid_date = lambda **kwargs: None
    cfg = {"enabled": True, "username": "u", "password": "p", "meter_id": "3000012345"}

    result = service.run_nightly_sync(cfg, tzinfo=pnd_module.ZoneInfo("Europe/Prague"))

    assert requested == [(date(2026, 3, 29), date(2026, 4, 4))]
    assert result["validated_days"] == 7

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
