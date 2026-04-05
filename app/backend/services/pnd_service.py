from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Callable, Optional
from zoneinfo import ZoneInfo

import httpx


PND_DASHBOARD_URL = "https://pnd.cezdistribuce.cz/cezpnd2/external/dashboard/view"
PND_DATA_ENDPOINT = "https://pnd.cezdistribuce.cz/cezpnd2/external/data"
DEFAULT_TZ = "Europe/Prague"
PND_LOGIN_PLACEHOLDERS = ("Zadejte svůj e-mail", "Zadejte své heslo", 'name="username"', 'name="password"', 'id="loginForm"')
PND_DASHBOARD_MARKERS = ("NamÄ›Ĺ™enĂˇ data", "Naměřená data", "Namerena data")


class PNDServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        stage: str,
        details: Optional[dict[str, Any]] = None,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.stage = stage
        self.details = details or {}
        self.status_code = status_code

    def to_detail(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "stage": self.stage,
            "details": self.details,
        }


@dataclass
class PNDExportBundle:
    portal_version: str | None = None
    json_data: Optional[dict[str, Any]] = None
    consumption_csv: Optional[str] = None
    production_csv: Optional[str] = None
    raw_metadata: Optional[dict[str, Any]] = None


class HttpSessionPNDPortalClient:
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("uvicorn.error")

    def verify(self, pnd_cfg: dict[str, Any], probe_date: date) -> dict[str, Any]:
        with self._session(pnd_cfg) as client:
            dashboard_html = self._request(client, "GET", PND_DASHBOARD_URL, stage="verify").text
            _ensure_dashboard_contract(dashboard_html, stage="verify")
            portal_version = self._extract_portal_version(dashboard_html)
            bundle = self._fetch_range_bundle(client, pnd_cfg, probe_date, probe_date, stage="verify", portal_version=portal_version)
            contract = _inspect_json_payload(bundle.json_data or {}, stage="verify")
            return {
                "ok": True,
                "stage": "verify",
                "message": "Prihlaseni do PND probehlo uspesne a datovy kontrakt odpovida ocekavanemu formatu.",
                "details": {
                    "portal_version": portal_version,
                    "transport": "httpx",
                    "data_endpoint": PND_DATA_ENDPOINT,
                    "meter_id": str(pnd_cfg.get("meter_id", "")).strip(),
                    "probe_date": probe_date.isoformat(),
                    "recognized_series": contract["recognized_series"],
                    "unknown_series": contract["unknown_series"],
                    "interval_count": contract["interval_count"],
                },
            }

    def fetch_range(self, pnd_cfg: dict[str, Any], start_date: date, end_date: date) -> PNDExportBundle:
        with self._session(pnd_cfg) as client:
            dashboard_html = self._request(client, "GET", PND_DASHBOARD_URL, stage="fetch").text
            _ensure_dashboard_contract(dashboard_html, stage="fetch")
            portal_version = self._extract_portal_version(dashboard_html)
            return self._fetch_range_bundle(client, pnd_cfg, start_date, end_date, stage="fetch", portal_version=portal_version)

    def _fetch_range_bundle(
        self,
        client,
        pnd_cfg: dict[str, Any],
        start_date: date,
        end_date: date,
        *,
        stage: str,
        portal_version: str | None,
    ) -> PNDExportBundle:
        payload = self._build_payload(pnd_cfg, start_date, end_date)
        response = self._request(client, "POST", PND_DATA_ENDPOINT, stage=stage, json=payload)
        if response.status_code != 200:
            raise PNDServiceError(
                "PND_API_FETCH_FAILED",
                f"PND endpoint vratil HTTP {response.status_code}.",
                stage=stage,
                details={"response_excerpt": response.text[:500], "status_code": response.status_code},
                status_code=503,
            )
        try:
            json_payload = response.json()
        except ValueError as exc:
            raise PNDServiceError(
                "PND_API_INVALID_JSON",
                "PND endpoint nevratil validni JSON.",
                stage=stage,
                details={"response_excerpt": response.text[:500]},
                status_code=503,
            ) from exc

        if not isinstance(json_payload, dict):
            raise PNDServiceError(
                "PND_API_INVALID_PAYLOAD",
                "PND endpoint vratil neocekavany datovy format.",
                stage=stage,
                details={"payload_type": type(json_payload).__name__},
                status_code=503,
            )

        _raise_for_payload_error(
            json_payload,
            stage=stage,
            meter_id=payload["electrometerId"],
            start_date=start_date,
            end_date=end_date,
        )

        return PNDExportBundle(
            portal_version=portal_version,
            json_data=json_payload,
            raw_metadata={
                "interval_from": payload["intervalFrom"],
                "interval_to": payload["intervalTo"],
                "meter_id": payload["electrometerId"],
            },
        )

    def _request(self, client, method: str, url: str, *, stage: str, **kwargs):
        try:
            return client.request(method, url, **kwargs)
        except httpx.TimeoutException as exc:
            raise PNDServiceError(
                "PND_NETWORK_TIMEOUT",
                "Vyprsel timeout pri komunikaci s PND.",
                stage=stage,
                details={"url": url, "error": str(exc)},
                status_code=504,
            ) from exc
        except httpx.RequestError as exc:
            raise PNDServiceError(
                "PND_NETWORK_ERROR",
                "Nepodarilo se spojit s PND endpointem.",
                stage=stage,
                details={"url": url, "error": str(exc)},
                status_code=503,
            ) from exc

    def _session(self, pnd_cfg: dict[str, Any]):
        username = pnd_cfg.get("username", "")
        password = pnd_cfg.get("password", "")
        client = httpx.Client(
            follow_redirects=True,
            timeout=30.0,
            headers={
                "User-Agent": "Elektroapp-PND/1.0",
                "Accept": "text/html,application/json,*/*",
            },
        )

        class _SessionContext:
            def __enter__(self_inner):
                response = self._request(client, "GET", PND_DASHBOARD_URL, stage="login")
                if response.status_code >= 400:
                    raise PNDServiceError(
                        "PND_LOGIN_PAGE_UNAVAILABLE",
                        f"PND login page vratila HTTP {response.status_code}.",
                        stage="login",
                        status_code=503,
                    )

                execution = _extract_execution_token(response.text)
                login_url = str(response.url)
                login_payload = {
                    "username": username,
                    "password": password,
                    "execution": execution,
                    "_eventId": "submit",
                    "geolocation": "",
                }
                login_response = self._request(client, "POST", login_url, stage="login", data=login_payload)
                if login_response.status_code >= 400:
                    raise PNDServiceError(
                        "PND_LOGIN_FAILED",
                        f"PND login endpoint vratil HTTP {login_response.status_code}.",
                        stage="login",
                        details={"status_code": login_response.status_code},
                        status_code=401,
                    )
                if _is_login_form_present(login_response.text):
                    portal_message = _extract_login_error(login_response.text)
                    raise PNDServiceError(
                        "PND_LOGIN_FAILED",
                        "Nepodarilo se prihlasit do PND.",
                        stage="login",
                        details={
                            "portal_message": portal_message,
                            "final_url": str(login_response.url),
                            "response_excerpt": login_response.text[:500],
                        },
                        status_code=401,
                    )
                return client

            def __exit__(self_inner, exc_type, exc, tb):
                client.close()

        return _SessionContext()

    def _extract_portal_version(self, html: str) -> str | None:
        match = re.search(r"Verze aplikace:\s*([^<\n]+)", html)
        if not match:
            return None
        return match.group(1).strip() or None

    def _build_payload(self, pnd_cfg: dict[str, Any], start_date: date, end_date: date) -> dict[str, Any]:
        # Deterministic request contract inferred for the PND data endpoint.
        return {
            "format": "chart",
            "idAssembly": -1003,
            "idDeviceSet": None,
            "intervalFrom": start_date.strftime("%d.%m.%Y 00:00"),
            "intervalTo": (end_date + timedelta(days=1)).strftime("%d.%m.%Y 00:00"),
            "compareFrom": None,
            "opmId": None,
            "electrometerId": str(pnd_cfg.get("meter_id", "")).strip(),
        }


def _collect_payload_messages(payload: Any) -> list[str]:
    collected: list[str] = []
    interesting_keys = {"message", "messages", "error", "errors", "detail", "details", "title", "description", "reason"}

    def visit(value: Any, key: str | None = None):
        if len(collected) >= 20:
            return
        if isinstance(value, str):
            text = value.strip()
            if text:
                collected.append(text)
            return
        if isinstance(value, dict):
            for nested_key, nested_value in value.items():
                if nested_key in interesting_keys or isinstance(nested_value, (dict, list, str)):
                    visit(nested_value, nested_key)
            return
        if isinstance(value, list):
            for item in value:
                visit(item, key)

    if isinstance(payload, dict):
        for nested_key, nested_value in payload.items():
            if nested_key in interesting_keys or isinstance(nested_value, (dict, list, str)):
                visit(nested_value, nested_key)
    return collected


def _raise_for_payload_error(
    payload: dict[str, Any],
    *,
    stage: str,
    meter_id: str,
    start_date: date,
    end_date: date,
):
    messages = _collect_payload_messages(payload)
    joined = " | ".join(message.lower() for message in messages)
    details = {
        "messages": messages,
        "payload_keys": sorted(payload.keys()),
        "meter_id": meter_id,
        "range": {"from": start_date.isoformat(), "to": end_date.isoformat()},
    }

    if any(token in joined for token in ("session", "prihlas", "login", "autent")):
        raise PNDServiceError(
            "PND_LOGIN_FAILED",
            "PND odmitlo datovy pozadavek, session neni platna.",
            stage=stage,
            details=details,
            status_code=401,
        )

    if any(token in joined for token in ("elektromer", "electrometer", "elm", "nenalezen", "not found", "invalid meter", "neplatn")):
        raise PNDServiceError(
            "PND_METER_NOT_FOUND",
            "Zadany meter_id v PND neexistuje nebo neni pristupny.",
            stage=stage,
            details=details,
            status_code=400,
        )

    if any(token in joined for token in ("nejsou k dispozici", "neni k dispozici", "not available", "zatim nebyla publikovana", "nebyla publikovana", "no data")):
        raise PNDServiceError(
            "PND_DATA_NOT_AVAILABLE",
            "Data pro pozadovane obdobi zatim nejsou v PND k dispozici.",
            stage=stage,
            details=details,
            status_code=409,
        )

    if payload.get("success") is False or payload.get("ok") is False:
        raise PNDServiceError(
            "PND_API_FETCH_FAILED",
            "PND endpoint vratil chybovy stav.",
            stage=stage,
            details=details,
            status_code=503,
        )


def _extract_execution_token(html: str) -> str:
    match = re.search(r'name="execution"\s+value="([^"]+)"', html)
    if not match:
        match = re.search(r'value="([^"]+)"\s+name="execution"', html)
    if not match:
        raise PNDServiceError(
            "PND_LOGIN_TOKEN_MISSING",
            "Na prihlasovaci strance chybi token 'execution'.",
            stage="login",
            status_code=503,
        )
    return match.group(1)


def _is_login_success(html: str) -> bool:
    return any(marker in html for marker in PND_DASHBOARD_MARKERS)


def _is_login_form_present(html: str) -> bool:
    return any(marker in html for marker in PND_LOGIN_PLACEHOLDERS)


def _ensure_dashboard_contract(html: str, *, stage: str):
    if _is_login_form_present(html):
        portal_message = _extract_login_error(html)
        raise PNDServiceError(
            "PND_LOGIN_FAILED",
            "PND po prihlaseni stale vraci login stranku, session neni navazana.",
            stage=stage,
            details={
                "portal_message": portal_message,
                "missing_html_marker": "Namerena data",
            },
            status_code=401,
        )
    if any(marker in html for marker in PND_DASHBOARD_MARKERS):
        return
    raise PNDServiceError(
        "PND_PORTAL_CHANGED",
        "PND dashboard po prihlaseni neobsahuje ocekavany marker 'Namerena data'.",
        stage=stage,
        details={"missing_html_marker": "Namerena data"},
        status_code=503,
    )


def _extract_login_error(html: str) -> str | None:
    for pattern in (
        r'class="alertWidget__content">([^<]+)<',
        r'class="formError">([^<]+)<',
        r'<div[^>]*class="[^"]*errors[^"]*"[^>]*>([^<]+)<',
        r'<div[^>]*class="[^"]*alert[^"]*"[^>]*>([^<]+)<',
    ):
        match = re.search(pattern, html)
        if match:
            return match.group(1).strip()
    return None


def _utc_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    normalized = str(value).replace("\xa0", "").replace(" ", "").replace(",", ".")
    normalized = re.sub(r"[^0-9\.\-]", "", normalized)
    if normalized == "":
        return None
    return float(normalized)


def _parse_pnd_timestamp(value: Any, tz: ZoneInfo) -> datetime:
    raw = str(value).strip()
    if not raw:
        raise ValueError("Missing PND timestamp")
    match = re.match(r"^(\d{2}\.\d{2}\.\d{4})\s+24:00(?::00)?$", raw)
    if match:
        base = datetime.strptime(match.group(1), "%d.%m.%Y").replace(tzinfo=tz)
        return base + timedelta(days=1)
    for fmt in ("%d.%m.%Y %H:%M:%S", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=tz)
        except ValueError:
            continue
    raise ValueError(f"Unsupported timestamp: {raw}")


def _inspect_json_payload(data: dict[str, Any], *, stage: str, tz_name: str = DEFAULT_TZ) -> dict[str, Any]:
    tz = ZoneInfo(tz_name)
    series = data.get("series")
    if not isinstance(series, list):
        raise PNDServiceError(
            "PND_PORTAL_CHANGED",
            "PND payload neobsahuje pole 'series' v ocekavanem formatu.",
            stage=stage,
            details={"payload_keys": sorted(data.keys())},
            status_code=503,
        )
    if not series:
        raise PNDServiceError(
            "PND_DATA_NOT_AVAILABLE",
            "PND pro pozadovane obdobi nevratilo zadne intervalove hodnoty.",
            stage=stage,
            details={"payload_keys": sorted(data.keys())},
            status_code=409,
        )

    merged: dict[str, dict[str, Any]] = {}
    recognized_series: list[str] = []
    unknown_series: list[str] = []

    def process_points(points: list[Any], target_key: str):
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            ts_value, value = point[0], point[1]
            if value is None:
                continue
            try:
                if isinstance(ts_value, (int, float)):
                    interval_end = datetime.fromtimestamp(float(ts_value) / 1000, tz=tz)
                else:
                    interval_end = _parse_pnd_timestamp(ts_value, tz)
            except ValueError:
                continue
            interval_start = interval_end - timedelta(minutes=15)
            key = interval_start.isoformat()
            entry = merged.setdefault(
                key,
                {
                    "start": interval_start.isoformat(),
                    "end": interval_end.isoformat(),
                    "consumption_kwh": None,
                    "production_kwh": None,
                },
            )
            entry[target_key] = float(value)

    for item in series:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).lower()
        points = item.get("data", [])
        if not isinstance(points, list):
            continue
        if "+a" in name:
            recognized_series.append(name)
            process_points(points, "consumption_kwh")
        elif "-a" in name:
            recognized_series.append(name)
            process_points(points, "production_kwh")
        elif name:
            unknown_series.append(name)

    if not recognized_series:
        raise PNDServiceError(
            "PND_PORTAL_CHANGED",
            "PND payload obsahuje neznama datova pole, parser je nedokaze interpretovat.",
            stage=stage,
            details={"series_names": unknown_series or [str(item.get("name", "")) for item in series if isinstance(item, dict)]},
            status_code=503,
        )

    if not merged:
        raise PNDServiceError(
            "PND_PORTAL_CHANGED",
            "PND payload obsahuje rozpoznane serie, ale bez citelnych 15min intervalu.",
            stage=stage,
            details={"recognized_series": recognized_series},
            status_code=503,
        )

    return {
        "merged": merged,
        "recognized_series": sorted(set(recognized_series)),
        "unknown_series": sorted(set(unknown_series)),
        "interval_count": len(merged),
    }


def _normalize_json_series(data: dict[str, Any], *, fetched_at: str, raw_refs: dict[str, str], tz_name: str = DEFAULT_TZ) -> dict[str, dict[str, Any]]:
    inspected = _inspect_json_payload(data, stage="normalize", tz_name=tz_name)
    merged = inspected["merged"]

    by_day: dict[str, list[dict[str, Any]]] = {}
    for interval in sorted(merged.values(), key=lambda row: row["start"]):
        by_day.setdefault(interval["start"][:10], []).append(interval)

    if not by_day:
        raise PNDServiceError(
            "PND_DATA_NOT_AVAILABLE",
            "PND payload neobsahuje zadne ulozitelne intervaly.",
            stage="normalize",
            status_code=409,
        )

    return {
        day_key: {
            "date": day_key,
            "source": "pnd-cez-api",
            "interval_minutes": 15,
            "fetched_at": fetched_at,
            "raw_refs": raw_refs,
            "recognized_series": inspected["recognized_series"],
            "unknown_series": inspected["unknown_series"],
            "intervals": intervals,
            "totals": {
                "consumption_kwh": round(sum(item.get("consumption_kwh") or 0.0 for item in intervals), 6),
                "production_kwh": round(sum(item.get("production_kwh") or 0.0 for item in intervals), 6),
            },
        }
        for day_key, intervals in by_day.items()
    }


def _normalize_csv_series(csv_text: str, value_key: str, tz: ZoneInfo) -> dict[str, dict[str, Any]]:
    reader = csv.reader(csv_text.splitlines(), delimiter=";")
    parsed: dict[str, dict[str, Any]] = {}
    for row in reader:
        if len(row) < 2 or row[0].strip().lower().startswith("datum"):
            continue
        try:
            interval_end = _parse_pnd_timestamp(row[0], tz)
        except ValueError:
            continue
        value = _parse_float(row[1])
        if value is None:
            continue
        interval_start = interval_end - timedelta(minutes=15)
        key = interval_start.isoformat()
        entry = parsed.setdefault(
            key,
            {
                "start": interval_start.isoformat(),
                "end": interval_end.isoformat(),
                "consumption_kwh": None,
                "production_kwh": None,
            },
        )
        entry[value_key] = value
    return parsed


def normalize_pnd_interval_exports(
    consumption_csv: str,
    production_csv: str,
    *,
    fetched_at: str,
    raw_refs: dict[str, str],
    portal_version: str | None = None,
    tz_name: str = DEFAULT_TZ,
) -> dict[str, dict[str, Any]]:
    tz = ZoneInfo(tz_name)
    merged: dict[str, dict[str, Any]] = {}
    for key, entry in _normalize_csv_series(consumption_csv, "consumption_kwh", tz).items():
        merged[key] = entry
    for key, entry in _normalize_csv_series(production_csv, "production_kwh", tz).items():
        target = merged.setdefault(
            key,
            {
                "start": entry["start"],
                "end": entry["end"],
                "consumption_kwh": None,
                "production_kwh": None,
            },
        )
        target["production_kwh"] = entry["production_kwh"]

    by_day: dict[str, list[dict[str, Any]]] = {}
    for interval in sorted(merged.values(), key=lambda item: item["start"]):
        by_day.setdefault(interval["start"][:10], []).append(interval)

    return {
        day_key: {
            "date": day_key,
            "source": "pnd-cez-csv",
            "interval_minutes": 15,
            "fetched_at": fetched_at,
            "portal_version": portal_version,
            "raw_refs": raw_refs,
            "intervals": intervals,
            "totals": {
                "consumption_kwh": round(sum(item.get("consumption_kwh") or 0.0 for item in intervals), 6),
                "production_kwh": round(sum(item.get("production_kwh") or 0.0 for item in intervals), 6),
            },
        }
        for day_key, intervals in by_day.items()
    }


class PNDService:
    def __init__(
        self,
        root_dir: Path,
        *,
        logger: Optional[logging.Logger] = None,
        client_factory: Optional[Callable[[], Any]] = None,
        now_fn: Optional[Callable[[], str]] = None,
    ):
        self.root_dir = Path(root_dir)
        self.raw_dir = self.root_dir / "raw"
        self.normalized_dir = self.root_dir / "normalized"
        self.status_path = self.root_dir / "status.json"
        self.logger = logger or logging.getLogger("uvicorn.error")
        self.client_factory = client_factory or (lambda: HttpSessionPNDPortalClient(logger=self.logger))
        self.now_fn = now_fn or _utc_now
        self._ensure_dirs()

    def _ensure_dirs(self):
        self.root_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.normalized_dir.mkdir(parents=True, exist_ok=True)

    def _load_status(self) -> dict[str, Any]:
        if not self.status_path.exists():
            return {}
        try:
            return json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _save_status(self, payload: dict[str, Any]):
        self.status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_cache_status(self) -> dict[str, Any]:
        files = sorted(self.normalized_dir.glob("*.json"))
        days = [path.stem for path in files if re.match(r"^\d{4}-\d{2}-\d{2}$", path.stem)]
        return {
            "dir": str(self.root_dir),
            "days_count": len(days),
            "cached_from": days[0] if days else None,
            "cached_to": days[-1] if days else None,
            "size_bytes": sum(path.stat().st_size for path in files) if files else 0,
        }

    def get_status(self, cfg: Optional[dict[str, Any]] = None, *, pnd_cfg: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        status = self._load_status()
        effective_cfg = pnd_cfg if isinstance(pnd_cfg, dict) else (cfg.get("pnd", {}) if isinstance(cfg, dict) else {})
        configured = bool(effective_cfg.get("username") and effective_cfg.get("password") and effective_cfg.get("meter_id"))
        cache_status = self.get_cache_status()
        state = self._derive_state(bool(effective_cfg.get("enabled", False)), configured, status, cache_status)
        return {
            "enabled": bool(effective_cfg.get("enabled", False)),
            "configured": configured,
            "healthy": bool(status.get("healthy", False)),
            "last_verify_at": status.get("last_verify_at"),
            "last_sync_at": status.get("last_sync_at"),
            "last_error": status.get("last_error"),
            "portal_version": status.get("portal_version"),
            "last_job": status.get("last_job"),
            **cache_status,
            **state,
        }

    def has_day(self, date_str: str) -> bool:
        path = self.normalized_dir / f"{date_str}.json"
        if not path.exists():
            return False
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return bool(payload.get("intervals"))
        except (OSError, json.JSONDecodeError):
            return False

    def verify(self, pnd_cfg: dict[str, Any]) -> dict[str, Any]:
        self._validate_config(pnd_cfg)
        probe_date = datetime.now(ZoneInfo(DEFAULT_TZ)).date() - timedelta(days=1)
        result = self.client_factory().verify(pnd_cfg, probe_date)
        fetched_at = self.now_fn()
        self._save_status(
            {
                **self._load_status(),
                **self.get_cache_status(),
                "healthy": True,
                "last_verify_at": fetched_at,
                "portal_version": result.get("details", {}).get("portal_version"),
                "last_error": None,
                "last_job": {
                    "type": "verify",
                    "ok": True,
                    "finished_at": fetched_at,
                    "message": result.get("message"),
                    "probe_date": probe_date.isoformat(),
                },
            }
        )
        return {
            "ok": True,
            "stage": "verify",
            "message": result.get("message") or "PND verify probehlo uspesne.",
            "details": result.get("details", {}),
        }

    def fetch_day(self, pnd_cfg: dict[str, Any], target_date: date, *, reason: str = "manual") -> dict[str, Any]:
        return self.fetch_range(pnd_cfg, target_date, target_date, reason=reason)

    def run_nightly_sync(self, pnd_cfg: dict[str, Any], *, tzinfo=None) -> dict[str, Any]:
        tz = tzinfo or ZoneInfo(DEFAULT_TZ)
        target_date = datetime.now(tz).date() - timedelta(days=1)
        if self.has_day(target_date.isoformat()):
            return {"ok": True, "skipped": True, "reason": "already_cached", "date": target_date.isoformat()}
        try:
            return self.fetch_day(pnd_cfg, target_date, reason="nightly")
        except PNDServiceError as exc:
            self.record_error(exc, job_type="nightly", extra={"date": target_date.isoformat()})
            raise

    def fetch_range(self, pnd_cfg: dict[str, Any], start_date: date, end_date: date, *, reason: str) -> dict[str, Any]:
        self._validate_config(pnd_cfg)
        if end_date < start_date:
            raise PNDServiceError(
                "PND_INVALID_DATE_RANGE",
                "Koncove datum nesmi byt mensi nez pocatecni datum.",
                stage="fetch",
                details={"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
                status_code=400,
            )
        bundle = self.client_factory().fetch_range(pnd_cfg, start_date, end_date)
        fetched_at = self.now_fn()
        raw_refs = self._write_raw_files(start_date, end_date, bundle, fetched_at)
        if bundle.json_data is not None:
            normalized = _normalize_json_series(bundle.json_data, fetched_at=fetched_at, raw_refs=raw_refs)
        else:
            normalized = normalize_pnd_interval_exports(
                bundle.consumption_csv or "",
                bundle.production_csv or "",
                fetched_at=fetched_at,
                raw_refs=raw_refs,
                portal_version=bundle.portal_version,
            )
        if not normalized:
            raise PNDServiceError(
                "PND_DATA_NOT_AVAILABLE",
                "PND nevratilo zadne ulozitelne dny pro pozadovany rozsah.",
                stage="normalize",
                details={"from": start_date.isoformat(), "to": end_date.isoformat()},
                status_code=409,
            )
        saved_days = self._write_normalized_days(normalized)
        if saved_days <= 0:
            raise PNDServiceError(
                "PND_DATA_NOT_AVAILABLE",
                "PND nevratilo zadna data k ulozeni do cache.",
                stage="normalize",
                details={"from": start_date.isoformat(), "to": end_date.isoformat()},
                status_code=409,
            )
        self._save_status(
            {
                **self._load_status(),
                **self.get_cache_status(),
                "healthy": True,
                "last_sync_at": fetched_at,
                "portal_version": bundle.portal_version,
                "last_error": None,
                "last_job": {
                    "type": "sync",
                    "reason": reason,
                    "range": {"from": start_date.isoformat(), "to": end_date.isoformat()},
                    "ok": True,
                    "finished_at": fetched_at,
                    "saved_days": saved_days,
                },
            }
        )
        return {
            "ok": True,
            "saved_days": saved_days,
            "range": {"from": start_date.isoformat(), "to": end_date.isoformat()},
            "portal_version": bundle.portal_version,
        }

    def backfill(self, pnd_cfg: dict[str, Any], range_name: str, *, tzinfo=None) -> dict[str, Any]:
        self._validate_config(pnd_cfg)
        tz = tzinfo or ZoneInfo(DEFAULT_TZ)
        today = datetime.now(tz).date()
        yesterday = today - timedelta(days=1)
        started_at = self.now_fn()
        fetched_days = 0
        chunks = 0

        if range_name == "yesterday":
            ranges = [(yesterday, yesterday)]
        elif range_name == "week":
            ranges = [(yesterday - timedelta(days=6), yesterday)]
        elif range_name == "month":
            ranges = [(yesterday - timedelta(days=30), yesterday)]
        elif range_name == "year":
            ranges = [(yesterday - timedelta(days=364), yesterday)]
        elif range_name == "max":
            ranges = []
            chunk_end = yesterday
            for _ in range(10):
                chunk_start = max(date(2010, 1, 1), chunk_end - timedelta(days=364))
                ranges.append((chunk_start, chunk_end))
                if chunk_start <= date(2010, 1, 1):
                    break
                chunk_end = chunk_start - timedelta(days=1)
        else:
            raise PNDServiceError(
                "PND_INVALID_RANGE",
                f"Neznamy backfill range '{range_name}'.",
                stage="backfill",
                details={"range": range_name},
                status_code=400,
            )

        for start_date, end_date in ranges:
            chunks += 1
            try:
                result = self.fetch_range(pnd_cfg, start_date, end_date, reason=f"backfill:{range_name}")
            except PNDServiceError as exc:
                if range_name == "max" and exc.code == "PND_DATA_NOT_AVAILABLE":
                    break
                raise
            fetched_days += result["saved_days"]
            if range_name == "max" and result["saved_days"] == 0:
                break

        status = self.get_status(pnd_cfg=pnd_cfg)
        return {
            "accepted": True,
            "range": range_name,
            "started_at": started_at,
            "estimated_days": fetched_days,
            "chunks": chunks,
            "cached_from": status.get("cached_from"),
            "cached_to": status.get("cached_to"),
        }

    def record_error(self, exc: PNDServiceError, *, job_type: str, extra: Optional[dict[str, Any]] = None):
        now_iso = self.now_fn()
        self._save_status(
            {
                **self._load_status(),
                **self.get_cache_status(),
                "healthy": False,
                "last_error": {
                    "at": now_iso,
                    "code": exc.code,
                    "message": exc.message,
                    "stage": exc.stage,
                    "details": exc.details,
                },
                "last_job": {
                    "type": job_type,
                    "ok": False,
                    "finished_at": now_iso,
                    "error": exc.to_detail(),
                    **(extra or {}),
                },
            }
        )

    def get_data(self, start_date: str, end_date: str) -> dict[str, Any]:
        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()
        if end < start:
            raise PNDServiceError(
                "PND_INVALID_DATE_RANGE",
                "Koncove datum nesmi byt mensi nez pocatecni datum.",
                stage="data",
                details={"from": start_date, "to": end_date},
                status_code=400,
            )
        days = []
        cursor = start
        while cursor <= end:
            path = self.normalized_dir / f"{cursor.isoformat()}.json"
            if path.exists():
                days.append(json.loads(path.read_text(encoding="utf-8")))
            cursor += timedelta(days=1)
        return {"from": start_date, "to": end_date, "days": days, "days_count": len(days)}

    def _write_raw_files(self, start_date: date, end_date: date, bundle: PNDExportBundle, fetched_at: str) -> dict[str, str]:
        safe_stamp = fetched_at.replace(":", "-")
        base_name = f"{start_date.isoformat()}_{end_date.isoformat()}_{safe_stamp}"
        refs: dict[str, str] = {}
        if bundle.consumption_csv is not None:
            consumption_path = self.raw_dir / f"{base_name}_consumption.csv"
            consumption_path.write_text(bundle.consumption_csv, encoding="utf-8")
            refs["consumption_csv"] = consumption_path.name
        if bundle.production_csv is not None:
            production_path = self.raw_dir / f"{base_name}_production.csv"
            production_path.write_text(bundle.production_csv, encoding="utf-8")
            refs["production_csv"] = production_path.name
        if bundle.json_data is not None:
            json_path = self.raw_dir / f"{base_name}_data.json"
            json_path.write_text(json.dumps(bundle.json_data, ensure_ascii=False, indent=2), encoding="utf-8")
            refs["json_data"] = json_path.name
        meta_path = self.raw_dir / f"{base_name}_meta.json"
        meta_path.write_text(
            json.dumps(
                {
                    "fetched_at": fetched_at,
                    "portal_version": bundle.portal_version,
                    "metadata": bundle.raw_metadata or {},
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        refs["meta"] = meta_path.name
        return refs

    def _write_normalized_days(self, normalized_days: dict[str, dict[str, Any]]) -> int:
        saved_days = 0
        for day_key, payload in normalized_days.items():
            path = self.normalized_dir / f"{day_key}.json"
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            saved_days += 1
        return saved_days

    def _validate_config(self, pnd_cfg: dict[str, Any]):
        if not pnd_cfg.get("enabled"):
            raise PNDServiceError("PND_DISABLED", "PND integrace neni zapnuta.", stage="config", status_code=400)
        missing = [key for key in ("username", "password", "meter_id") if not str(pnd_cfg.get(key) or "").strip()]
        if missing:
            raise PNDServiceError(
                "PND_NOT_CONFIGURED",
                "PND integrace nema kompletni prihlasovaci udaje.",
                stage="config",
                details={"missing": missing},
                status_code=400,
            )

    def _derive_state(self, enabled: bool, configured: bool, status: dict[str, Any], cache_status: dict[str, Any]) -> dict[str, str | None]:
        if not enabled:
            return {"state": "disabled", "state_message": "PND integrace je vypnuta."}
        if not configured:
            return {"state": "not_configured", "state_message": "Dopln prihlasovaci udaje a meter_id pro PND."}

        last_error = status.get("last_error") or {}
        code = str(last_error.get("code") or "")
        if code == "PND_LOGIN_FAILED":
            return {"state": "login_failed", "state_message": "Prihlaseni do PND selhalo. Zkontroluj jmeno a heslo."}
        if code in {
            "PND_PORTAL_CHANGED",
            "PND_API_INVALID_JSON",
            "PND_API_INVALID_PAYLOAD",
            "PND_API_INVALID_SERIES",
            "PND_LOGIN_TOKEN_MISSING",
        }:
            return {"state": "portal_changed", "state_message": "Portal PND zmenil datovou strukturu nebo request contract."}
        if code == "PND_DATA_NOT_AVAILABLE":
            return {"state": "yesterday_not_available", "state_message": "Vcerejsi data zatim nejsou v PND publikovana."}
        if bool(status.get("healthy")) and int(cache_status.get("days_count") or 0) > 0:
            return {"state": "cache_ready", "state_message": "PND cache je validni a data jsou pripravená k pouziti."}
        if bool(status.get("healthy")):
            return {"state": "verified", "state_message": "PND verify probehlo, ale cache zatim neobsahuje zadne dny."}
        return {"state": "error", "state_message": "PND integrace je nakonfigurovana, ale posledni operace skoncila chybou."}


def should_run_pnd_window(now: datetime, *, start_hour: int = 2, end_hour: int = 7) -> bool:
    start_hour = max(0, min(23, int(start_hour)))
    end_hour = max(start_hour, min(23, int(end_hour)))
    return time(start_hour, 0) <= now.timetz().replace(tzinfo=None) <= time(end_hour, 59)
