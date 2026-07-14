from __future__ import annotations

from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import logging
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from urllib.parse import quote

import requests


DEFAULT_DIP_URL = "https://dip.cezdistribuce.cz/irj/portal/prehled-uctu/"
DIP_OVERVIEW_URL = "https://dip.cezdistribuce.cz/irj/portal/prehled-om/"
CAS_CLIENT_ID = "fjR3ZL9zrtsNcDQF.onpremise.dip.sap.dipcezdistribucecz.prod"
CAS_AUTHORIZE_URL = "https://cas.cez.cz/cas/oidc/authorize"


class DIPServiceError(Exception):
    def __init__(self, code: str, message: str, *, status_code: int = 502, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class _FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.forms: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None

    def handle_starttag(self, tag, attrs):
        attrs_dict = dict(attrs)
        if tag == "form":
            self.current = {"action": attrs_dict.get("action", ""), "method": attrs_dict.get("method", "post"), "inputs": []}
        elif tag == "input" and self.current is not None:
            self.current["inputs"].append(attrs_dict)

    def handle_endtag(self, tag):
        if tag == "form" and self.current is not None:
            self.forms.append(self.current)
            self.current = None


class HttpSessionDIPPortalClient:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("uvicorn.error")

    def _login(self, cfg: dict[str, Any]) -> tuple[requests.Session, str]:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/131.0 Safari/537.36",
            "Accept-Language": "cs-CZ,cs;q=0.9",
        })
        redirect_uri = str(cfg.get("url") or DIP_OVERVIEW_URL)
        authorize_url = (
            f"{CAS_AUTHORIZE_URL}?response_type=code&redirect_uri={quote(redirect_uri, safe='')}"
            f"&client_id={CAS_CLIENT_ID}&scope=openid"
        )
        response = session.get(authorize_url, timeout=30, allow_redirects=True)
        response.raise_for_status()
        parser = _FormParser()
        parser.feed(response.text)
        password_form = next(
            (form for form in parser.forms if any(str(item.get("type", "")).lower() == "password" for item in form["inputs"])),
            None,
        )
        if not password_form:
            raise DIPServiceError("DIP_LOGIN_FORM_CHANGED", "ČEZ CAS neobsahuje očekávaný přihlašovací formulář.")
        payload = {item.get("name"): item.get("value", "") for item in password_form["inputs"] if item.get("name")}
        payload.update({"username": cfg.get("username", ""), "password": cfg.get("password", ""), "_eventId": "submit", "geolocation": ""})
        action = urljoin(response.url, password_form["action"] or response.url)
        response = session.post(action, data=payload, timeout=30, allow_redirects=True)
        response.raise_for_status()
        if "cas.cez.cz/cas/login" in response.url or "name=\"password\"" in response.text:
            raise DIPServiceError("DIP_LOGIN_FAILED", "Přihlášení do DIP selhalo.", status_code=401)
        token_response = session.get(
            "https://dip.cezdistribuce.cz/irj/portal/rest-auth-api?path=/token/get",
            headers={"Accept": "application/json, text/plain, */*", "Referer": response.url},
            timeout=30,
        )
        token_response.raise_for_status()
        token = (token_response.json() or {}).get("data")
        if not token:
            raise DIPServiceError("DIP_TOKEN_FAILED", "DIP nevrátil autorizační token.")
        return session, str(token)

    @staticmethod
    def _api(session: requests.Session, token: str, path: str, *, method: str = "GET", payload=None):
        response = session.request(
            method,
            f"https://dip.cezdistribuce.cz/irj/portal/{path}",
            headers={"X-Request-Token": token, "Accept": "application/json, text/plain, */*"},
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        envelope = response.json()
        if not isinstance(envelope, dict) or int(envelope.get("statusCode", 200)) >= 400:
            raise DIPServiceError("DIP_API_ERROR", f"DIP API selhalo pro {path}.")
        return envelope.get("data")

    @staticmethod
    def _address(value):
        return value.get("adresaComplete") if isinstance(value, dict) else None

    def _normalize_point(self, detail, readings, signals, shutdowns, signal_notifications):
        facts = detail.get("faktaOM") or {}
        slices = facts.get("casoveRezy") or []
        current = slices[0] if slices else {}
        meter = (detail.get("elektromery") or [{}])[0]
        supply = detail.get("su") or {}
        payment_methods = []
        for item in supply.get("listPlateb") or []:
            method = item.get("aktualniZpusobPlatby") or {}
            payment_methods.append({"type": item.get("typ"), "method": method.get("text")})
        return {
            "supply_point_number": detail.get("cislo"),
            "ean": detail.get("ean"),
            "kind": detail.get("typText") or detail.get("druhTxt"),
            "note": detail.get("note"),
            "customer_name": detail.get("jmenoOP"),
            "supply_address": self._address(detail.get("adresa") or {}),
            "permanent_address": self._address(detail.get("permanentAddress") or {}),
            "mailing_address": self._address(detail.get("mailingAddress") or {}),
            "billing_address": self._address(detail.get("billingAddress") or {}),
            "contact": {
                "first_name": (detail.get("contactOM") or {}).get("firstName"),
                "last_name": (detail.get("contactOM") or {}).get("lastName"),
                "email": (detail.get("contactOM") or {}).get("email"),
                "telephone": (detail.get("contactOM") or {}).get("telephone"),
            },
            "technical": {
                "voltage_level": facts.get("napetovaHladina"),
                "metering_type": facts.get("typMereni"),
                "metering_type_from": current.get("typMereniOd"),
                "meter_id": meter.get("sernr"),
                "last_reading_date": facts.get("datumPoslednihoOdectu"),
                "last_vt_kwh": facts.get("posledniStavVt"),
                "last_nt_kwh": facts.get("posledniStavNt"),
                "billing_reading_date": facts.get("datumFakturacnihoOdectu"),
                "phases": current.get("pocetFazi"),
                "phases_from": current.get("pocetFaziOd"),
                "breaker_amps": current.get("hlavniJistic"),
                "breaker_from": current.get("hlavniJisticOd"),
                "billed_breaker_amps": current.get("hlavniJisticFakt"),
                "billed_breaker_from": current.get("hlavniJisticFaktOd"),
                "breaker_characteristic": facts.get("jisticCharakteristika"),
                "distribution_tariff": current.get("sazbaDistribuce") or (detail.get("anlage_Dist") or {}).get("sazba"),
                "distribution_tariff_from": current.get("sazbaDistribuceOd"),
                "installed_power_kw": facts.get("instalovanyVykon"),
                "reserved_power_kw": facts.get("rezervovanyVykon"),
                "max_delivered_power_kw": current.get("pmaxVy"),
                "max_delivered_power_from": current.get("pmaxVyOd"),
                "accumulation": detail.get("embeddedAccumulationIntoProduction"),
            },
            "contract": {
                "distribution_status": detail.get("stavSmlouvyDistribuceTxt"),
                "type": (detail.get("scenarDodavky") or {}).get("scenarDodavkyText"),
                "supplier": supply.get("dodavatelTxt"),
                "valid_from": supply.get("platnostOd"),
                "electronic_invoice": supply.get("elFaktura"),
                "payment_methods": payment_methods,
            },
            "appliances": [item.get("spotrebic") for item in detail.get("spotrebice") or [] if item.get("spotrebic")],
            "readings": readings or [],
            "tariff_switching": (signals or {}).get("signals", []) if isinstance(signals, dict) else [],
            "outage_notifications": (shutdowns or {}).get("notifSettings", {}) if isinstance(shutdowns, dict) else {},
            "planned_outages": (shutdowns or {}).get("shutdowns", []) if isinstance(shutdowns, dict) else [],
            "tariff_notifications": signal_notifications or {},
            "internal": {"uid": detail.get("uid"), "partner": detail.get("partner"), "metering_point_id": detail.get("celm")},
        }

    def fetch_profile(self, cfg: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
        session, token = self._login(cfg)
        listing = self._api(
            session,
            token,
            "vyhledani-om?path=/vyhledaniom/zakladniInfo/50/PREHLED_OM_CELEK",
            method="POST",
            payload={"nekontrolovatPrislusnostOM": False},
        ) or {}
        blocks = ((listing.get("vstelleBlocks") or {}).get("blocks") or [])
        summaries = [point for block in blocks for point in block.get("vstelles", [])]
        points = []
        raw_details = []
        for summary in summaries:
            uid = summary.get("uid")
            ean = summary.get("ean")
            if not uid or not ean:
                continue
            detail = self._api(session, token, f"prehled-om?path=supply-point-detail/{uid}") or {}
            readings = self._api(session, token, f"prehled-om?path=supply-point-detail/meter-reading-history/{uid}/false", method="POST", payload={}) or []
            signals = self._api(session, token, f"prehled-om?path=supply-point-detail/signals/{ean}") or {}
            shutdowns = self._api(session, token, f"prehled-om?path=supply-point-detail/shutdowns/{detail.get('cislo')}/{detail.get('partner')}/{detail.get('celm')}") or {}
            notifications = self._api(session, token, f"prehled-om?path=supply-point-detail/signal-notifications/{detail.get('partner')}") or {}
            points.append(self._normalize_point(detail, readings, signals, shutdowns, notifications))
            raw_details.append({"summary": summary, "detail": detail, "readings": readings, "signals": signals, "shutdowns": shutdowns, "signal_notifications": notifications})
        if not points:
            raise DIPServiceError("DIP_NO_SUPPLY_POINTS", "DIP nevrátil žádná odběrná místa.")
        primary_id = str(cfg.get("primary_supply_point_id") or "")
        primary = next((item for item in points if item.get("supply_point_number") == primary_id or item.get("ean") == primary_id), None)
        if primary is None:
            primary = next((item for item in points if str(item.get("kind", "")).casefold() == "spotřeba"), points[0])
        profile = {"supply_points": points, "primary_supply_point": primary, "primary_supply_point_id": primary.get("supply_point_number")}
        return profile, {"listing": listing, "points": raw_details}


class DIPService:
    def __init__(self, root_dir: Path, *, logger=None, client=None):
        self.root_dir = Path(root_dir)
        self.raw_dir = self.root_dir / "raw"
        self.profile_path = self.root_dir / "profile.json"
        self.status_path = self.root_dir / "status.json"
        self.logger = logger or logging.getLogger("uvicorn.error")
        self.client = client or HttpSessionDIPPortalClient(self.logger)
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: dict[str, Any]):
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_profile(self) -> dict[str, Any]:
        if not self.profile_path.exists():
            return {}
        try:
            return json.loads(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def get_status(self, cfg: dict[str, Any]) -> dict[str, Any]:
        status = {}
        if self.status_path.exists():
            try:
                status = json.loads(self.status_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        dip_cfg = cfg.get("dip", {}) if isinstance(cfg.get("dip"), dict) else {}
        return {
            "enabled": bool(dip_cfg.get("enabled")),
            "configured": bool(dip_cfg.get("username") and dip_cfg.get("password")),
            "profile_available": bool(self.get_profile()),
            **status,
        }

    def sync(self, cfg: dict[str, Any]) -> dict[str, Any]:
        dip_cfg = cfg.get("dip", {}) if isinstance(cfg.get("dip"), dict) else {}
        if not dip_cfg.get("enabled"):
            raise DIPServiceError("DIP_DISABLED", "DIP integrace není zapnuta.", status_code=400)
        if not dip_cfg.get("username") or not dip_cfg.get("password"):
            raise DIPServiceError("DIP_NOT_CONFIGURED", "DIP nemá vyplněné přihlašovací údaje.", status_code=400)
        fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        try:
            profile, raw_payload = self.client.fetch_profile(dip_cfg)
            raw_path = self.raw_dir / f"profile-{fetched_at.replace(':', '-')}.json"
            raw_path.write_text(json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            for stale_path in sorted(self.raw_dir.glob("profile-*.json"), reverse=True)[10:]:
                stale_path.unlink(missing_ok=True)
            normalized = {**profile, "fetched_at": fetched_at, "source": "dip"}
            self._write_json(self.profile_path, normalized)
            self._write_json(self.status_path, {"healthy": True, "last_sync_at": fetched_at, "last_error": None})
            return {"ok": True, "profile": normalized}
        except DIPServiceError as exc:
            self._write_json(self.status_path, {"healthy": False, "last_sync_at": fetched_at, "last_error": {"code": exc.code, "message": exc.message}})
            raise
        except requests.RequestException as exc:
            error = DIPServiceError("DIP_NETWORK_ERROR", "Síťová komunikace s DIP selhala.", details={"error": str(exc)})
            self._write_json(self.status_path, {"healthy": False, "last_sync_at": fetched_at, "last_error": {"code": error.code, "message": error.message}})
            raise error from exc
