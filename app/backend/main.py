from fastapi import FastAPI, Body, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import requests
import yaml
import os
import json
import threading
import time as time_module
import re
from html.parser import HTMLParser
import calendar
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

app = FastAPI(title="Elektroapp API")

CONFIG_FILE = "config.yaml"
HA_OPTIONS_FILE = Path("/data/options.json")
CONFIG_DIR = Path("/config")
_storage_env = os.getenv("ELEKTROAPP_STORAGE")
if _storage_env:
    STORAGE_DIR = Path(_storage_env)
else:
    STORAGE_DIR = CONFIG_DIR / "elektroapp" if CONFIG_DIR.exists() else Path("/data")
PRICES_CACHE = {}
PRICES_CACHE_PROVIDER = {}
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = (STORAGE_DIR / "prices-cache") if STORAGE_DIR else (Path(__file__).parent / "cache")
CONSUMPTION_CACHE_DIR = (
    STORAGE_DIR / "consumption-cache" if STORAGE_DIR else (Path(__file__).parent / "consumption-cache")
)
CONSUMPTION_CACHE_TTL_SECONDS = 600
EXPORT_CACHE_DIR = (
    STORAGE_DIR / "export-cache" if STORAGE_DIR else (Path(__file__).parent / "export-cache")
)
EXPORT_CACHE_TTL_SECONDS = 600
SERIES_CACHE_KEY_VERSION = 2
OPTIONS_BACKUP_FILE = STORAGE_DIR / "options.json"
FEES_HISTORY_FILE = STORAGE_DIR / "fees-history.json"
APP_VERSION = os.getenv("ADDON_VERSION", os.getenv("APP_VERSION", "dev"))
logger = logging.getLogger("uvicorn.error")

PRICE_PROVIDER_SPOT = "spotovaelektrina"
PRICE_PROVIDER_OTE = "ote"
DEFAULT_PRICE_PROVIDER = PRICE_PROVIDER_SPOT
OTE_PUBLIC_URL = "https://www.ote-cr.cz/services/PublicDataService"
OTE_PUBLIC_URL_HTTP = "http://www.ote-cr.cz/services/PublicDataService"
OTE_SOAP_ACTION_GET_DAM_PRICE_PERIOD_E = "http://www.ote-cr.cz/schema/service/public/GetDamPricePeriodE"
CNB_RATES_URL = "https://api.cnb.cz/cnbapi/exrates/daily"
OTE_PUBLIC_NS = "{http://www.ote-cr.cz/schema/service/public}"
SOAP_FAULT_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"
PRAGUE_TZ = ZoneInfo("Europe/Prague")
OTE_FAILURE_RETRY_SECONDS = 600
OTE_UNAVAILABLE_UNTIL_TS = 0.0

# --- Povolit CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # můžeš zpřísnit jen na frontend doménu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Konfigurace ---
def parse_vt_periods(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    periods = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            continue
        start_str, end_str = part.split("-", 1)
        try:
            start = int(start_str.strip())
            end = int(end_str.strip())
        except ValueError:
            continue
        periods.append([start, end])
    return periods

def normalize_price_provider(value):
    if not isinstance(value, str):
        return DEFAULT_PRICE_PROVIDER
    normalized = value.strip().lower()
    if normalized in {PRICE_PROVIDER_SPOT, "spotovaelektrina.cz", "spot"}:
        return PRICE_PROVIDER_SPOT
    if normalized in {PRICE_PROVIDER_OTE, "ote-cr.cz", "ote.cz", "otecr"}:
        return PRICE_PROVIDER_OTE
    return DEFAULT_PRICE_PROVIDER

def get_price_provider(cfg):
    if not isinstance(cfg, dict):
        return DEFAULT_PRICE_PROVIDER
    return normalize_price_provider(cfg.get("price_provider"))

def mark_ote_unavailable(reason):
    global OTE_UNAVAILABLE_UNTIL_TS
    OTE_UNAVAILABLE_UNTIL_TS = max(OTE_UNAVAILABLE_UNTIL_TS, time_module.time() + OTE_FAILURE_RETRY_SECONDS)
    logger.warning("OTE marked unavailable for %ss: %s", OTE_FAILURE_RETRY_SECONDS, reason)

def get_ote_backoff_remaining_seconds():
    remaining = int(OTE_UNAVAILABLE_UNTIL_TS - time_module.time())
    return max(0, remaining)

def is_ote_unavailable():
    return get_ote_backoff_remaining_seconds() > 0

def merge_config(base, override):
    if not isinstance(base, dict):
        base = {}
    if not isinstance(override, dict):
        return base
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = merge_config(base.get(key), value)
        else:
            base[key] = value
    return base

def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0

def normalize_dph_percent(value):
    dph_value = _safe_float(value)
    if dph_value <= 0:
        return 0.0
    if dph_value <= 2:
        return max(0.0, (dph_value - 1) * 100)
    return dph_value

def build_fee_snapshot(cfg):
    poplatky = cfg.get("poplatky", {}) if isinstance(cfg.get("poplatky"), dict) else {}
    distribuce = poplatky.get("distribuce", {}) if isinstance(poplatky.get("distribuce"), dict) else {}
    fixni = cfg.get("fixni", {}) if isinstance(cfg.get("fixni"), dict) else {}
    fixni_denni = fixni.get("denni", {}) if isinstance(fixni.get("denni"), dict) else {}
    fixni_mesicni = fixni.get("mesicni", {}) if isinstance(fixni.get("mesicni"), dict) else {}
    prodej = cfg.get("prodej", {}) if isinstance(cfg.get("prodej"), dict) else {}
    oze_value = poplatky.get("oze")
    if oze_value is None:
        oze_value = poplatky.get("poze", 0)
    return {
        "dph_percent": normalize_dph_percent(cfg.get("dph", 0)),
        "kwh_fees": {
            "komodita_sluzba": _safe_float(poplatky.get("komodita_sluzba", 0)),
            "oze": _safe_float(oze_value),
            "dan": _safe_float(poplatky.get("dan", 0)),
            "systemove_sluzby": _safe_float(poplatky.get("systemove_sluzby", 0)),
            "distribuce": {
                "NT": _safe_float(distribuce.get("NT", 0)),
                "VT": _safe_float(distribuce.get("VT", 0)),
            },
        },
        "fixed": {
            "daily": {
                "staly_plat": _safe_float(fixni_denni.get("staly_plat", 0)),
            },
            "monthly": {
                "provoz_nesitove_infrastruktury": _safe_float(
                    fixni_mesicni.get("provoz_nesitove_infrastruktury", 0)
                ),
                "jistic": _safe_float(fixni_mesicni.get("jistic", 0)),
            },
        },
        "prodej": {
            "koeficient_snizeni_ceny": _safe_float(prodej.get("koeficient_snizeni_ceny", 0)),
        },
    }

def load_fee_history():
    if not FEES_HISTORY_FILE.exists():
        return []
    try:
        with open(FEES_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []

def save_fee_history(history):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEES_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f)

def normalize_fee_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        snapshot = {}

    if "kwh_fees" in snapshot or "fixed" in snapshot:
        kwh_fees = snapshot.get("kwh_fees", {}) if isinstance(snapshot.get("kwh_fees"), dict) else {}
        distribuce = kwh_fees.get("distribuce", {}) if isinstance(kwh_fees.get("distribuce"), dict) else {}
        fixed = snapshot.get("fixed", {}) if isinstance(snapshot.get("fixed"), dict) else {}
        daily = fixed.get("daily", {}) if isinstance(fixed.get("daily"), dict) else {}
        monthly = fixed.get("monthly", {}) if isinstance(fixed.get("monthly"), dict) else {}
        prodej = snapshot.get("prodej", {}) if isinstance(snapshot.get("prodej"), dict) else {}
        return {
            "dph_percent": normalize_dph_percent(snapshot.get("dph_percent", snapshot.get("dph", 0))),
            "kwh_fees": {
                "komodita_sluzba": _safe_float(kwh_fees.get("komodita_sluzba", 0)),
                "oze": _safe_float(kwh_fees.get("oze", 0)),
                "dan": _safe_float(kwh_fees.get("dan", 0)),
                "systemove_sluzby": _safe_float(kwh_fees.get("systemove_sluzby", 0)),
                "distribuce": {
                    "NT": _safe_float(distribuce.get("NT", 0)),
                    "VT": _safe_float(distribuce.get("VT", 0)),
                },
            },
            "fixed": {
                "daily": {
                    "staly_plat": _safe_float(daily.get("staly_plat", 0)),
                },
                "monthly": {
                    "provoz_nesitove_infrastruktury": _safe_float(
                        monthly.get("provoz_nesitove_infrastruktury", 0)
                    ),
                    "jistic": _safe_float(monthly.get("jistic", 0)),
                },
            },
            "prodej": {
                "koeficient_snizeni_ceny": _safe_float(
                    prodej.get("koeficient_snizeni_ceny", snapshot.get("koeficient_snizeni_ceny", 0))
                ),
            },
        }

    poplatky = snapshot.get("poplatky", {}) if isinstance(snapshot.get("poplatky"), dict) else {}
    distribuce = poplatky.get("distribuce", {}) if isinstance(poplatky.get("distribuce"), dict) else {}
    fixni = snapshot.get("fixni", {}) if isinstance(snapshot.get("fixni"), dict) else {}
    fixni_denni = fixni.get("denni", {}) if isinstance(fixni.get("denni"), dict) else {}
    fixni_mesicni = fixni.get("mesicni", {}) if isinstance(fixni.get("mesicni"), dict) else {}
    prodej = snapshot.get("prodej", {}) if isinstance(snapshot.get("prodej"), dict) else {}
    oze_value = poplatky.get("oze")
    if oze_value is None:
        oze_value = poplatky.get("poze", 0)
    return {
        "dph_percent": normalize_dph_percent(snapshot.get("dph", 0)),
        "kwh_fees": {
            "komodita_sluzba": _safe_float(poplatky.get("komodita_sluzba", 0)),
            "oze": _safe_float(oze_value),
            "dan": _safe_float(poplatky.get("dan", 0)),
            "systemove_sluzby": _safe_float(poplatky.get("systemove_sluzby", 0)),
            "distribuce": {
                "NT": _safe_float(distribuce.get("NT", 0)),
                "VT": _safe_float(distribuce.get("VT", 0)),
            },
        },
        "fixed": {
            "daily": {
                "staly_plat": _safe_float(fixni_denni.get("staly_plat", 0)),
            },
            "monthly": {
                "provoz_nesitove_infrastruktury": _safe_float(
                    fixni_mesicni.get("provoz_nesitove_infrastruktury", 0)
                ),
                "jistic": _safe_float(fixni_mesicni.get("jistic", 0)),
            },
        },
        "prodej": {
            "koeficient_snizeni_ceny": _safe_float(
                prodej.get("koeficient_snizeni_ceny", snapshot.get("koeficient_snizeni_ceny", 0))
            ),
        },
    }

def ensure_fee_history(cfg, tzinfo):
    history = load_fee_history()
    history.sort(key=lambda x: x.get("effective_from", ""))
    today_date = datetime.now(tzinfo).date()
    today_str = today_date.strftime("%Y-%m-%d")
    snapshot = build_fee_snapshot(cfg)
    if not history:
        history = [{"effective_from": today_str, "snapshot": snapshot}]
        save_fee_history(history)
        return history
    current_record = None
    for record in history:
        try:
            record_from = datetime.strptime(record.get("effective_from", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if record_from > today_date:
            continue
        record_to = None
        record_to_str = record.get("effective_to")
        if record_to_str:
            try:
                record_to = datetime.strptime(record_to_str, "%Y-%m-%d").date()
            except ValueError:
                record_to = None
        if record_to and today_date > record_to:
            continue
        current_record = record
    if current_record:
        if current_record.get("snapshot") != snapshot:
            current_record["snapshot"] = snapshot
            save_fee_history(history)
        return history
    history.append({"effective_from": today_str, "snapshot": snapshot})
    save_fee_history(history)
    return history

def get_fee_snapshot_for_date(cfg, date_str, tzinfo):
    history = ensure_fee_history(cfg, tzinfo)
    if not history:
        return build_fee_snapshot(cfg)
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return history[-1].get("snapshot", build_fee_snapshot(cfg))
    candidate = None
    match = None
    for record in history:
        try:
            record_date = datetime.strptime(record.get("effective_from", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if record_date > target_date:
            break
        candidate = record
        record_to = None
        record_to_str = record.get("effective_to")
        if record_to_str:
            try:
                record_to = datetime.strptime(record_to_str, "%Y-%m-%d").date()
            except ValueError:
                record_to = None
        if record_to is None or target_date <= record_to:
            match = record
    if match:
        return match.get("snapshot", build_fee_snapshot(cfg))
    if candidate:
        return candidate.get("snapshot", build_fee_snapshot(cfg))
    return history[0].get("snapshot", build_fee_snapshot(cfg))

def load_config():
    cfg = {}
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}

    options_files = [HA_OPTIONS_FILE, OPTIONS_BACKUP_FILE]
    for options_path in options_files:
        if not options_path.exists():
            continue
        try:
            with open(options_path, "r", encoding="utf-8") as f:
                options = json.load(f)
            cfg = merge_config(cfg, options)
            if options_path == HA_OPTIONS_FILE and STORAGE_DIR:
                STORAGE_DIR.mkdir(parents=True, exist_ok=True)
                with open(OPTIONS_BACKUP_FILE, "w", encoding="utf-8") as f:
                    json.dump(options, f)
            break
        except Exception:
            continue

    if isinstance(cfg, dict):
        cfg["dph"] = normalize_dph_percent(cfg.get("dph", 0))
        cfg["price_provider"] = normalize_price_provider(cfg.get("price_provider"))
        tarif = cfg.get("tarif")
        if isinstance(tarif, dict):
            vt_periods = tarif.get("vt_periods")
            if isinstance(vt_periods, str):
                tarif["vt_periods"] = parse_vt_periods(vt_periods)
        poplatky = cfg.get("poplatky")
        if isinstance(poplatky, dict) and "oze" not in poplatky and "poze" in poplatky:
            poplatky["oze"] = poplatky.get("poze")
    return cfg

def get_local_tz(tz_name):
    try:
        return ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    except Exception:
        return datetime.now().astimezone().tzinfo

def parse_time_range(date_str, start_str, end_str, tzinfo):
    if date_str:
        try:
            start_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tzinfo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc
        end_local = start_local + timedelta(days=1)
    elif start_str and end_str:
        try:
            start_local = datetime.fromisoformat(start_str)
            end_local = datetime.fromisoformat(end_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid start/end format. Use ISO 8601, e.g. 2026-01-15T00:00:00+01:00.",
            ) from exc
        if start_local.tzinfo is None:
            start_local = start_local.replace(tzinfo=tzinfo)
        if end_local.tzinfo is None:
            end_local = end_local.replace(tzinfo=tzinfo)
    else:
        now_local = datetime.now(tzinfo)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)

def to_rfc3339(dt):
    return dt.isoformat().replace("+00:00", "Z")

def get_influx_cfg(cfg):
    influx = cfg.get("influxdb", {})
    required = ["host", "port", "database", "measurement", "field", "entity_id"]
    missing = [key for key in required if not influx.get(key)]
    if missing:
        raise HTTPException(status_code=500, detail=f"Missing influxdb config keys: {', '.join(missing)}")
    return influx

def get_export_entity_id(cfg):
    influx = cfg.get("influxdb", {}) if isinstance(cfg.get("influxdb"), dict) else {}
    return influx.get("export_entity_id")

def get_sell_coefficient_kwh(cfg, fee_snapshot=None):
    prodej = None
    if isinstance(fee_snapshot, dict):
        prodej = fee_snapshot.get("prodej") if isinstance(fee_snapshot.get("prodej"), dict) else None
    if not isinstance(prodej, dict):
        prodej = cfg.get("prodej", {}) if isinstance(cfg.get("prodej"), dict) else {}
    coef_mwh = _safe_float(prodej.get("koeficient_snizeni_ceny", 0))
    return coef_mwh / 1000.0

def influx_query(influx, query):
    host = influx["host"]
    port = influx.get("port", 8086)
    db = influx["database"]
    url = f"http://{host}:{port}/query"
    params = {"db": db, "q": query, "epoch": "s"}
    username = influx.get("username")
    password = influx.get("password")
    auth = None
    if username and password and password != "CHANGE_ME":
        auth = (username, password)
    r = requests.get(url, params=params, auth=auth, timeout=10)
    r.raise_for_status()
    data = r.json()
    if data.get("results") and data["results"][0].get("error"):
        raise HTTPException(status_code=500, detail=data["results"][0]["error"])
    return data

class PriceTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.row = []
        self.rows = []
        self._current_data = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == "prices":
                self.in_table = True
        if self.in_table and tag == "td":
            self.in_td = True
            self._current_data = []

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        if self.in_table and tag == "td":
            self.in_td = False
            cell = "".join(self._current_data).strip()
            self.row.append(cell)
        if self.in_table and tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []

    def handle_data(self, data):
        if self.in_td:
            self._current_data.append(data)

def parse_price_html(html_text):
    parser = PriceTableParser()
    parser.feed(html_text)
    rows = []
    for row in parser.rows:
        if len(row) < 2:
            continue
        time_str = row[0]
        price_text = row[1]
        m = re.search(r"([0-9][0-9\s\xa0]*)", price_text)
        if not m:
            continue
        digits = re.sub(r"[^\d]", "", m.group(1))
        if not digits:
            continue
        price_czk = int(digits)
        rows.append((time_str, price_czk))
    return rows

def get_prices_cache_path(date_str):
    return CACHE_DIR / f"prices-{date_str}.json"

def get_prices_cache_meta_path(date_str):
    return CACHE_DIR / f"prices-meta-{date_str}.json"

def load_prices_cache(date_str):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = get_prices_cache_path(date_str)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def load_prices_cache_meta(date_str):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    meta_path = get_prices_cache_meta_path(date_str)
    if not meta_path.exists():
        return None
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None

def save_prices_cache(date_str, entries, provider=None):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = get_prices_cache_path(date_str)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    if provider:
        meta_path = get_prices_cache_meta_path(date_str)
        meta_payload = {
            "provider": normalize_price_provider(provider),
            "fetched_at": datetime.utcnow().isoformat() + "Z",
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f)
    logger.info("Saved prices cache for %s to %s", date_str, path)

def get_cached_price_provider(date_str):
    provider = PRICES_CACHE_PROVIDER.get(date_str)
    if provider:
        return provider
    meta = load_prices_cache_meta(date_str)
    if isinstance(meta, dict):
        provider = normalize_price_provider(meta.get("provider"))
    else:
        # Legacy cache files did not include metadata; those came from spotovaelektrina.cz.
        provider = PRICE_PROVIDER_SPOT
    PRICES_CACHE_PROVIDER[date_str] = provider
    return provider

def is_price_cache_provider_match(date_str, provider):
    return get_cached_price_provider(date_str) == normalize_price_provider(provider)

def clear_prices_cache_for_date(date_str, remove_files=True):
    PRICES_CACHE.pop(date_str, None)
    PRICES_CACHE_PROVIDER.pop(date_str, None)
    if not remove_files:
        return
    for path in (get_prices_cache_path(date_str), get_prices_cache_meta_path(date_str)):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            continue

def build_consumption_cache_key(influx):
    return {
        "cache_version": SERIES_CACHE_KEY_VERSION,
        "entity_id": influx.get("entity_id"),
        "measurement": influx.get("measurement"),
        "field": influx.get("field"),
        "interval": influx.get("interval", "15m"),
        "retention_policy": influx.get("retention_policy"),
        "timezone": influx.get("timezone"),
    }

def load_consumption_cache(date_str, cache_key):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = CONSUMPTION_CACHE_DIR / f"consumption-{date_str}.json"
    if not path.exists():
        return None, None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None, None, None
    if not isinstance(payload, dict):
        return None, None, None
    meta = payload.get("meta", {})
    if meta.get("key") != cache_key:
        return None, None, None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None, None
    return data, path, meta

def save_consumption_cache(date_str, cache_key, data):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CONSUMPTION_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CONSUMPTION_CACHE_DIR / f"consumption-{date_str}.json"
    payload = {
        "meta": {"key": cache_key, "fetched_at": datetime.utcnow().isoformat() + "Z"},
        "data": data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    logger.info("Saved consumption cache for %s to %s", date_str, path)

def build_export_cache_key(influx, export_entity_id):
    return {
        "cache_version": SERIES_CACHE_KEY_VERSION,
        "entity_id": export_entity_id,
        "measurement": influx.get("measurement"),
        "field": influx.get("field"),
        "interval": influx.get("interval", "15m"),
        "retention_policy": influx.get("retention_policy"),
        "timezone": influx.get("timezone"),
    }

def load_export_cache(date_str, cache_key):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_CACHE_DIR / f"export-{date_str}.json"
    if not path.exists():
        return None, None, None
    try:
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except Exception:
        return None, None, None
    if not isinstance(payload, dict):
        return None, None, None
    meta = payload.get("meta", {})
    if meta.get("key") != cache_key:
        return None, None, None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None, None
    return data, path, meta

def save_export_cache(date_str, cache_key, data):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = EXPORT_CACHE_DIR / f"export-{date_str}.json"
    payload = {
        "meta": {"key": cache_key, "fetched_at": datetime.utcnow().isoformat() + "Z"},
        "data": data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    logger.info("Saved export cache for %s to %s", date_str, path)

def is_cache_fresh(path, ttl_seconds):
    if not path or ttl_seconds <= 0:
        return False
    try:
        age = time_module.time() - path.stat().st_mtime
    except OSError:
        return False
    return age < ttl_seconds

def is_today_date(date_str, tzinfo):
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    return date_obj == datetime.now(tzinfo).date()

def is_date_cache_complete(date_str, meta, tzinfo):
    if not isinstance(meta, dict):
        return False
    fetched_at_raw = meta.get("fetched_at")
    if not isinstance(fetched_at_raw, str):
        return False
    try:
        fetched_at_utc = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00")).astimezone(timezone.utc)
        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return False
    day_end_local = datetime.combine(date_obj + timedelta(days=1), datetime_time(0, 0), tzinfo)
    day_end_utc = day_end_local.astimezone(timezone.utc)
    return fetched_at_utc >= day_end_utc

def has_price_cache(date_str, provider=None):
    cached = load_prices_cache(date_str)
    if not cached:
        return False
    if provider:
        return is_price_cache_provider_match(date_str, provider)
    return True

def cache_status_for_dir(path, prefix):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return {"dir": str(path), "count": 0, "latest": None, "size_bytes": 0}
    files = []
    for file_path in path.glob(f"{prefix}-*.json"):
        suffix = file_path.stem.replace(f"{prefix}-", "", 1)
        if re.match(r"^\d{4}-\d{2}-\d{2}$", suffix):
            files.append(file_path)
    files.sort()
    latest = None
    total_size = 0
    if files:
        latest = files[-1].stem.replace(f"{prefix}-", "")
        total_size = sum(file_path.stat().st_size for file_path in files)
    return {"dir": str(path), "count": len(files), "latest": latest, "size_bytes": total_size}

def cache_status():
    return {
        "prices": cache_status_for_dir(CACHE_DIR, "prices"),
        "consumption": cache_status_for_dir(CONSUMPTION_CACHE_DIR, "consumption"),
        "export": cache_status_for_dir(EXPORT_CACHE_DIR, "export"),
    }

def build_entries_from_api(cfg, date_str, hours, fee_snapshot):
    entries = []
    for entry in hours:
        hour = entry["hour"]
        minute = entry.get("minute", 0)
        spot_kwh = entry["priceCZK"] / 1000
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_entries_from_ote(cfg, date_str, items, fee_snapshot, eur_to_czk_rate):
    entries = []
    for item in items:
        hour = item["hour"]
        minute = item["minute"]
        spot_kwh = (item["price_eur_mwh"] * eur_to_czk_rate) / 1000.0
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_entries_from_spot_html(cfg, date_str, fee_snapshot):
    logger.info("Fetching historical prices from HTML for %s", date_str)
    url = f"https://spotovaelektrina.cz/denni-ceny/{date_str}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    rows = parse_price_html(r.text)
    entries = []
    for time_str, price_czk in rows:
        hour, minute = map(int, time_str.split(":"))
        spot_kwh = price_czk / 1000
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_ote_query(start_date, end_date):
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pub="http://www.ote-cr.cz/schema/service/public">
  <soapenv:Header/>
  <soapenv:Body>
    <pub:GetDamPricePeriodE>
      <pub:StartDate>{start_date}</pub:StartDate>
      <pub:EndDate>{end_date}</pub:EndDate>
      <pub:PeriodResolution>PT15M</pub:PeriodResolution>
    </pub:GetDamPricePeriodE>
  </soapenv:Body>
</soapenv:Envelope>"""

def fetch_ote_prices_xml(start_date, end_date):
    query = build_ote_query(start_date.isoformat(), end_date.isoformat())
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "Accept": "text/xml",
        "SOAPAction": OTE_SOAP_ACTION_GET_DAM_PRICE_PERIOD_E,
    }
    last_exc = None
    for url in (OTE_PUBLIC_URL, OTE_PUBLIC_URL_HTTP):
        try:
            logger.info("Fetching OTE prices from %s for %s..%s", url, start_date, end_date)
            response = requests.post(url, data=query.encode("utf-8"), headers=headers, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("OTE request failed via %s: %s", url, exc)

    if last_exc:
        raise last_exc
    raise HTTPException(status_code=502, detail="OTE request failed.")

def parse_ote_prices_xml(xml_text):
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise HTTPException(status_code=502, detail="OTE response could not be parsed.") from exc

    fault = root.find(f".//{SOAP_FAULT_NS}Fault")
    if fault is not None:
        fault_string = fault.findtext("faultstring") or "Unknown OTE SOAP fault."
        raise HTTPException(status_code=502, detail=f"OTE request failed: {fault_string}")

    rows_by_date = {}
    for item in root.findall(f".//{OTE_PUBLIC_NS}Item"):
        date_text = item.findtext(f"{OTE_PUBLIC_NS}Date")
        period_index_text = item.findtext(f"{OTE_PUBLIC_NS}PeriodIndex")
        price_text = item.findtext(f"{OTE_PUBLIC_NS}Price")
        if not date_text or not period_index_text or not price_text:
            continue
        try:
            current_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            period_index = int(period_index_text)
            if period_index < 1 or period_index > 100:
                continue
            price_eur_mwh = float(price_text)
        except ValueError:
            continue

        start_of_day_local = datetime.combine(current_date, datetime_time(0), tzinfo=PRAGUE_TZ)
        slot_utc = start_of_day_local.astimezone(timezone.utc) + timedelta(minutes=(period_index - 1) * 15)
        slot_local = slot_utc.astimezone(PRAGUE_TZ)
        slot_date = slot_local.strftime("%Y-%m-%d")

        rows_by_date.setdefault(slot_date, []).append(
            {
                "hour": slot_local.hour,
                "minute": slot_local.minute,
                "price_eur_mwh": price_eur_mwh,
            }
        )

    for date_str in rows_by_date:
        rows_by_date[date_str].sort(key=lambda item: (item["hour"], item["minute"]))
    return rows_by_date

def extract_eur_czk_from_cnb_payload(payload):
    if not isinstance(payload, dict):
        return None
    rates = payload.get("rates")
    if not isinstance(rates, list):
        return None
    for rate in rates:
        if not isinstance(rate, dict):
            continue
        if str(rate.get("currencyCode", "")).upper() != "EUR":
            continue
        amount = _safe_float(rate.get("amount", 1))
        amount = amount if amount > 0 else 1.0
        value = _safe_float(rate.get("rate"))
        if value > 0:
            return value / amount
    return None

def get_eur_czk_rate_for_date(day):
    for offset in range(7):
        query_day = day - timedelta(days=offset)
        try:
            response = requests.get(CNB_RATES_URL, params={"date": query_day.isoformat()}, timeout=10)
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        eur_czk = extract_eur_czk_from_cnb_payload(payload)
        if eur_czk is not None:
            return eur_czk
    raise HTTPException(status_code=502, detail="CNB FX rate EUR/CZK is not available.")

def get_ote_entries_for_dates(cfg, dates, tzinfo):
    if not dates:
        return {}
    date_objects = sorted({datetime.strptime(date_str, "%Y-%m-%d").date() for date_str in dates})
    xml_text = fetch_ote_prices_xml(date_objects[0], date_objects[-1])
    rows_by_date = parse_ote_prices_xml(xml_text)

    entries_by_date = {}
    eur_cache = {}
    for date_obj in date_objects:
        date_str = date_obj.strftime("%Y-%m-%d")
        if date_obj not in eur_cache:
            eur_cache[date_obj] = get_eur_czk_rate_for_date(date_obj)
        fee_snapshot = get_fee_snapshot_for_date(cfg, date_str, tzinfo)
        entries_by_date[date_str] = build_entries_from_ote(
            cfg,
            date_str,
            rows_by_date.get(date_str, []),
            fee_snapshot,
            eur_cache[date_obj],
        )
    return entries_by_date

def apply_fee_snapshot(entries, cfg, fee_snapshot):
    if not entries:
        return []
    adjusted = []
    for entry in entries:
        hour = entry.get("hour", 0)
        spot = entry.get("spot", 0)
        final = calculate_final_price(spot, hour, cfg, fee_snapshot)
        adjusted.append({**entry, "final": final})
    return adjusted

def get_prices_for_date(cfg, date_str, tzinfo, force_refresh=False, include_neighbor_live=False):
    provider = get_price_provider(cfg)
    effective_provider = provider
    fee_snapshot = get_fee_snapshot_for_date(cfg, date_str, tzinfo)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now(tzinfo).date()
    tomorrow = today + timedelta(days=1)
    is_live_date = date_obj in (today, tomorrow)

    if not force_refresh:
        cached = PRICES_CACHE.get(date_str)
        if cached:
            if not is_live_date or is_price_cache_provider_match(date_str, provider):
                return apply_fee_snapshot(cached, cfg, fee_snapshot)
            cached_provider = get_cached_price_provider(date_str)
            logger.info(
                "Skipping in-memory cache for %s due to provider switch (%s -> %s)",
                date_str,
                cached_provider,
                provider,
            )

        cached = load_prices_cache(date_str)
        if cached:
            cached_provider = get_cached_price_provider(date_str)
            if is_live_date and cached_provider != normalize_price_provider(provider):
                logger.info(
                    "Skipping file cache for %s due to provider switch (%s -> %s)",
                    date_str,
                    cached_provider,
                    provider,
                )
            else:
                PRICES_CACHE[date_str] = cached
                PRICES_CACHE_PROVIDER[date_str] = cached_provider
                logger.info("Prices cache hit for %s", date_str)
                return apply_fee_snapshot(cached, cfg, fee_snapshot)
    logger.info("Prices cache miss for %s", date_str)

    entries = []
    if is_live_date:
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        requested_dates = []
        if date_obj == today:
            requested_dates.append(today_str)
            if include_neighbor_live:
                requested_dates.append(tomorrow_str)
        elif date_obj == tomorrow:
            requested_dates.append(tomorrow_str)

        needs_today = today_str in requested_dates
        needs_tomorrow = tomorrow_str in requested_dates
        today_entries = []
        tomorrow_entries = []
        today_provider = provider
        tomorrow_provider = provider
        if provider == PRICE_PROVIDER_OTE:
            if not force_refresh and is_ote_unavailable():
                logger.info(
                    "Skipping OTE live fetch for %s/%s due to cooldown (%ss left)",
                    today_str,
                    tomorrow_str,
                    get_ote_backoff_remaining_seconds(),
                )
            else:
                try:
                    entries_by_date = get_ote_entries_for_dates(cfg, requested_dates, tzinfo)
                    today_entries = entries_by_date.get(today_str, [])
                    tomorrow_entries = entries_by_date.get(tomorrow_str, [])
                except Exception as exc:
                    mark_ote_unavailable(exc)
                    logger.warning("OTE live prices fetch failed for %s/%s: %s", today_str, tomorrow_str, exc)

            if needs_today and not today_entries:
                cached_today = load_prices_cache(today_str)
                if cached_today and is_price_cache_provider_match(today_str, PRICE_PROVIDER_OTE):
                    today_entries = cached_today
                    today_provider = PRICE_PROVIDER_OTE
                    PRICES_CACHE[today_str] = cached_today
                    PRICES_CACHE_PROVIDER[today_str] = PRICE_PROVIDER_OTE
                    logger.info("Using cached OTE prices for %s", today_str)
            if needs_tomorrow and not tomorrow_entries:
                cached_tomorrow = load_prices_cache(tomorrow_str)
                if cached_tomorrow and is_price_cache_provider_match(tomorrow_str, PRICE_PROVIDER_OTE):
                    tomorrow_entries = cached_tomorrow
                    tomorrow_provider = PRICE_PROVIDER_OTE
                    PRICES_CACHE[tomorrow_str] = cached_tomorrow
                    PRICES_CACHE_PROVIDER[tomorrow_str] = PRICE_PROVIDER_OTE
                    logger.info("Using cached OTE prices for %s", tomorrow_str)
        else:
            try:
                data = get_spot_prices()
                today_snapshot = get_fee_snapshot_for_date(cfg, today_str, tzinfo)
                tomorrow_snapshot = get_fee_snapshot_for_date(cfg, tomorrow_str, tzinfo)
                today_entries = build_entries_from_api(cfg, today_str, data.get("hoursToday", []), today_snapshot)
                tomorrow_entries = build_entries_from_api(cfg, tomorrow_str, data.get("hoursTomorrow", []), tomorrow_snapshot)
            except Exception as exc:
                logger.warning("Spot live prices fetch failed for %s/%s: %s", today_str, tomorrow_str, exc)

            if needs_today and not today_entries:
                cached_today = load_prices_cache(today_str)
                if cached_today and is_price_cache_provider_match(today_str, PRICE_PROVIDER_SPOT):
                    today_entries = cached_today
                    today_provider = PRICE_PROVIDER_SPOT
                    PRICES_CACHE[today_str] = cached_today
                    PRICES_CACHE_PROVIDER[today_str] = PRICE_PROVIDER_SPOT
                    logger.info("Using cached spot prices for %s", today_str)
            if needs_tomorrow and not tomorrow_entries:
                cached_tomorrow = load_prices_cache(tomorrow_str)
                if cached_tomorrow and is_price_cache_provider_match(tomorrow_str, PRICE_PROVIDER_SPOT):
                    tomorrow_entries = cached_tomorrow
                    tomorrow_provider = PRICE_PROVIDER_SPOT
                    PRICES_CACHE[tomorrow_str] = cached_tomorrow
                    PRICES_CACHE_PROVIDER[tomorrow_str] = PRICE_PROVIDER_SPOT
                    logger.info("Using cached spot prices for %s", tomorrow_str)

        if needs_today and today_entries:
            PRICES_CACHE[today_str] = today_entries
            PRICES_CACHE_PROVIDER[today_str] = today_provider
            save_prices_cache(today_str, today_entries, provider=today_provider)
        if needs_tomorrow and tomorrow_entries:
            PRICES_CACHE[tomorrow_str] = tomorrow_entries
            PRICES_CACHE_PROVIDER[tomorrow_str] = tomorrow_provider
            save_prices_cache(tomorrow_str, tomorrow_entries, provider=tomorrow_provider)
        entries = today_entries if date_obj == today else tomorrow_entries
        if date_obj == today:
            effective_provider = today_provider
        elif date_obj == tomorrow:
            effective_provider = tomorrow_provider
    else:
        if provider == PRICE_PROVIDER_OTE:
            if not force_refresh and is_ote_unavailable():
                logger.info(
                    "Skipping OTE historical fetch for %s due to cooldown (%ss left)",
                    date_str,
                    get_ote_backoff_remaining_seconds(),
                )
            else:
                try:
                    entries_by_date = get_ote_entries_for_dates(cfg, [date_str], tzinfo)
                    entries = entries_by_date.get(date_str, [])
                except Exception as exc:
                    mark_ote_unavailable(exc)
                    logger.warning("OTE historical prices fetch failed for %s: %s", date_str, exc)
        elif provider == PRICE_PROVIDER_SPOT and not entries:
            try:
                entries = build_entries_from_spot_html(cfg, date_str, fee_snapshot)
                effective_provider = PRICE_PROVIDER_SPOT
            except Exception as exc:
                logger.warning("Spot historical prices fetch failed for %s: %s", date_str, exc)
                entries = []

    if entries:
        PRICES_CACHE[date_str] = entries
        PRICES_CACHE_PROVIDER[date_str] = effective_provider
        save_prices_cache(date_str, entries, provider=effective_provider)
    return apply_fee_snapshot(entries, cfg, fee_snapshot)

def build_price_map_for_date(cfg, date_str, tzinfo):
    entries = get_prices_for_date(cfg, date_str, tzinfo)
    price_map = {}
    price_map_utc = {}
    for entry in entries:
        time_local = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M")
        if time_local.tzinfo is None:
            time_local = time_local.replace(tzinfo=tzinfo)
        key_local = time_local.strftime("%Y-%m-%d %H:%M")
        key_utc = time_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        price_map[key_local] = {"spot": entry["spot"], "final": entry["final"]}
        price_map_utc[key_utc] = {"spot": entry["spot"], "final": entry["final"]}
    return price_map, price_map_utc

def calculate_daily_totals(cfg, date_str):
    consumption = get_consumption_points(cfg, date=date_str)
    tzinfo = consumption["tzinfo"]
    has_series = consumption.get("has_series", False)
    if not has_series:
        return {"kwh_total": None, "cost_total": None, "has_series": has_series}
    price_map, price_map_utc = build_price_map_for_date(cfg, date_str, tzinfo)

    total_kwh = 0.0
    total_cost = 0.0
    count = 0
    for entry in consumption["points"]:
        kwh = entry["kwh"]
        time_local = datetime.fromisoformat(entry["time"])
        key = time_local.strftime("%Y-%m-%d %H:%M")
        price = price_map.get(key)
        if price is None:
            time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
            key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
            price = price_map_utc.get(key_utc)
        final_price = price["final"] if price else None
        if kwh is not None and final_price is not None:
            total_kwh += kwh
            total_cost += kwh * final_price
            count += 1

    if count == 0:
        return {"kwh_total": None, "cost_total": None, "has_series": has_series}
    return {"kwh_total": round(total_kwh, 5), "cost_total": round(total_cost, 5), "has_series": has_series}

def calculate_daily_export_totals(cfg, date_str):
    export_entity_id = get_export_entity_id(cfg)
    if not export_entity_id:
        return {"export_kwh_total": None, "sell_total": None, "has_series": False}
    export = get_export_points(cfg, date=date_str)
    tzinfo = export["tzinfo"]
    has_series = export.get("has_series", False)
    if not has_series:
        return {"export_kwh_total": None, "sell_total": None, "has_series": has_series}
    price_map, price_map_utc = build_price_map_for_date(cfg, date_str, tzinfo)
    fee_snapshot = get_fee_snapshot_for_date(cfg, date_str, tzinfo)
    coef_kwh = get_sell_coefficient_kwh(cfg, fee_snapshot)

    total_kwh = 0.0
    total_sell = 0.0
    count = 0
    for entry in export["points"]:
        kwh = entry["kwh"]
        time_local = datetime.fromisoformat(entry["time"])
        key = time_local.strftime("%Y-%m-%d %H:%M")
        price = price_map.get(key)
        if price is None:
            time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
            key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
            price = price_map_utc.get(key_utc)
        spot_price = price["spot"] if price else None
        sell_price = spot_price - coef_kwh if spot_price is not None else None
        if kwh is not None and sell_price is not None:
            total_kwh += kwh
            total_sell += kwh * sell_price
            count += 1

    if count == 0:
        return {"export_kwh_total": None, "sell_total": None, "has_series": has_series}
    return {
        "export_kwh_total": round(total_kwh, 5),
        "sell_total": round(total_sell, 5),
        "has_series": has_series,
    }

def compute_fixed_breakdown_for_day(fee_snapshot, days_in_month):
    fixed = fee_snapshot.get("fixed", {})
    daily_fees = fixed.get("daily", {}) if isinstance(fixed.get("daily"), dict) else {}
    monthly_fees = fixed.get("monthly", {}) if isinstance(fixed.get("monthly"), dict) else {}
    dph_multiplier = 1 + (fee_snapshot.get("dph_percent", 0) / 100.0)
    daily_with_dph = {key: value * dph_multiplier for key, value in daily_fees.items()}
    monthly_with_dph = {
        key: (value / days_in_month) * dph_multiplier for key, value in monthly_fees.items()
    }
    return daily_with_dph, monthly_with_dph

def compute_monthly_billing(cfg, month_str, tzinfo, require_data=None):
    if not re.match(r"^\d{4}-\d{2}$", month_str):
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
    year, month_num = map(int, month_str.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]
    start_date = datetime(year, month_num, 1).date()
    today = datetime.now(tzinfo).date()
    if require_data is None:
        require_data = start_date.year == today.year and start_date.month == today.month

    actual_variable = 0.0
    actual_kwh = 0.0
    actual_export_kwh = 0.0
    actual_sell_total = 0.0
    days_with_data = 0
    export_days_with_data = 0
    fixed_total = 0.0
    fixed_breakdown = {"daily": {}, "monthly": {}}

    for day_offset in range(days_in_month):
        date_obj = start_date + timedelta(days=day_offset)
        date_str = date_obj.strftime("%Y-%m-%d")

        fee_snapshot = get_fee_snapshot_for_date(cfg, date_str, tzinfo)
        daily_fixed, monthly_fixed = compute_fixed_breakdown_for_day(fee_snapshot, days_in_month)
        for key, value in daily_fixed.items():
            fixed_breakdown["daily"][key] = fixed_breakdown["daily"].get(key, 0.0) + value
        for key, value in monthly_fixed.items():
            fixed_breakdown["monthly"][key] = fixed_breakdown["monthly"].get(key, 0.0) + value
        fixed_total += sum(daily_fixed.values()) + sum(monthly_fixed.values())

        if date_obj <= today:
            totals = calculate_daily_totals(cfg, date_str)
            if totals["kwh_total"] is not None:
                actual_kwh += totals["kwh_total"]
                actual_variable += totals["cost_total"]
                days_with_data += 1
            export_totals = calculate_daily_export_totals(cfg, date_str)
            if export_totals["export_kwh_total"] is not None:
                actual_export_kwh += export_totals["export_kwh_total"]
            if export_totals["sell_total"] is not None:
                actual_sell_total += export_totals["sell_total"]
                export_days_with_data += 1

    if days_with_data == 0 and start_date <= today and require_data:
        raise HTTPException(
            status_code=500,
            detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
        )

    if days_with_data == 0:
        actual = {
            "kwh_total": None,
            "variable_cost": None,
            "fixed_cost": None,
            "total_cost": None,
            "export_kwh_total": None,
            "sell_total": None,
            "net_total": None,
        }
        projected = {
            "variable_cost": None,
            "fixed_cost": None,
            "total_cost": None,
            "sell_total": None,
            "net_total": None,
        }
    else:
        projected_variable = (actual_variable / days_with_data) * days_in_month
        projected_sell_total = None
        if export_days_with_data > 0:
            projected_sell_total = (actual_sell_total / export_days_with_data) * days_in_month
        actual_sell_value = round(actual_sell_total, 5) if export_days_with_data > 0 else None
        actual_export_value = round(actual_export_kwh, 5) if export_days_with_data > 0 else None
        projected_sell_value = round(projected_sell_total, 5) if projected_sell_total is not None else None
        actual_total_cost = actual_variable + fixed_total
        projected_total_cost = projected_variable + fixed_total
        actual_net_total = actual_total_cost - (actual_sell_value or 0.0)
        projected_net_total = projected_total_cost - (projected_sell_value or 0.0)
        actual = {
            "kwh_total": round(actual_kwh, 5),
            "variable_cost": round(actual_variable, 5),
            "fixed_cost": round(fixed_total, 5),
            "total_cost": round(actual_total_cost, 5),
            "export_kwh_total": actual_export_value,
            "sell_total": actual_sell_value,
            "net_total": round(actual_net_total, 5),
        }
        projected = {
            "variable_cost": round(projected_variable, 5),
            "fixed_cost": round(fixed_total, 5),
            "total_cost": round(projected_total_cost, 5),
            "sell_total": projected_sell_value,
            "net_total": round(projected_net_total, 5),
        }
    fixed_breakdown["daily"] = {k: round(v, 5) for k, v in fixed_breakdown["daily"].items()}
    fixed_breakdown["monthly"] = {k: round(v, 5) for k, v in fixed_breakdown["monthly"].items()}

    return {
        "month": month_str,
        "days_in_month": days_in_month,
        "days_with_data": days_with_data,
        "actual": actual,
        "projected": projected,
        "fixed_breakdown": fixed_breakdown,
    }

def get_consumption_points(cfg, date=None, start=None, end=None):
    influx = get_influx_cfg(cfg)
    tzinfo = get_local_tz(influx.get("timezone"))
    cache_key = None
    cached = None
    cache_path = None
    cache_meta = None
    if date and not start and not end:
        cache_key = build_consumption_cache_key(influx)
        cached, cache_path, cache_meta = load_consumption_cache(date, cache_key)
        use_cached = False
        if cached:
            if is_today_date(date, tzinfo):
                use_cached = is_cache_fresh(cache_path, CONSUMPTION_CACHE_TTL_SECONDS)
            else:
                use_cached = is_date_cache_complete(date, cache_meta, tzinfo)
        if use_cached:
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = False
            return cached

    start_utc, end_utc = parse_time_range(date, start, end, tzinfo)

    rp = influx.get("retention_policy")
    measurement = influx["measurement"]
    from_clause = f'"{measurement}"' if not rp else f'"{rp}"."{measurement}"'
    field = influx["field"]
    entity_id = influx["entity_id"]
    interval = influx.get("interval", "15m")

    q = (
        f'SELECT last("{field}") AS "kwh_total" '
        f"FROM {from_clause} "
        f"WHERE time >= '{to_rfc3339(start_utc)}' AND time < '{to_rfc3339(end_utc)}' "
        f'AND "entity_id"=\'{entity_id}\' '
        f"GROUP BY time({interval}) fill(null)"
    )

    try:
        data = influx_query(influx, q)
    except Exception as exc:
        logger.warning("Influx consumption query failed (date=%s start=%s end=%s): %s", date, start, end, exc)
        if cached:
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = True
            return cached
        raise
    series = data.get("results", [{}])[0].get("series", [])
    has_series = bool(series)
    values = series[0]["values"] if series else []

    points = []
    prev_total = None
    start_utc_ts = int(start_utc.timestamp())
    for ts, total in values:
        if total is None:
            kwh = None
        elif prev_total is None:
            # Only treat the first interval (start of range) as "from zero".
            kwh = total if ts == start_utc_ts else None
        else:
            diff = total - prev_total
            if diff >= 0:
                kwh = diff
            else:
                # Some sensors restart the import counter when buying resumes later
                # in the same day. Treat the lower value as a new series baseline.
                kwh = total
        if total is not None:
            prev_total = total

        ts_dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        ts_local = ts_dt_utc.astimezone(tzinfo)
        points.append(
            {
                "time": ts_local.isoformat(),
                "time_utc": to_rfc3339(ts_dt_utc),
                "kwh_total": total,
                "kwh": kwh,
            }
        )

    result = {
        "range": {"start": to_rfc3339(start_utc), "end": to_rfc3339(end_utc)},
        "interval": interval,
        "entity_id": entity_id,
        "points": points,
        "tzinfo": tzinfo,
        "has_series": has_series,
        "from_cache": False,
        "cache_fallback": False,
    }
    if date and not start and not end and has_series:
        cache_payload = {
            "range": result["range"],
            "interval": result["interval"],
            "entity_id": result["entity_id"],
            "points": result["points"],
            "has_series": result["has_series"],
        }
        save_consumption_cache(date, cache_key, cache_payload)
    return result

def get_export_points(cfg, date=None, start=None, end=None):
    influx = get_influx_cfg(cfg)
    tzinfo = get_local_tz(influx.get("timezone"))
    export_entity_id = get_export_entity_id(cfg)
    if not export_entity_id:
        raise HTTPException(status_code=500, detail="Missing influxdb export_entity_id.")
    cache_key = None
    cached = None
    cache_path = None
    cache_meta = None
    if date and not start and not end:
        cache_key = build_export_cache_key(influx, export_entity_id)
        cached, cache_path, cache_meta = load_export_cache(date, cache_key)
        use_cached = False
        if cached:
            if is_today_date(date, tzinfo):
                use_cached = is_cache_fresh(cache_path, EXPORT_CACHE_TTL_SECONDS)
            else:
                use_cached = is_date_cache_complete(date, cache_meta, tzinfo)
        if use_cached:
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = False
            return cached

    start_utc, end_utc = parse_time_range(date, start, end, tzinfo)

    rp = influx.get("retention_policy")
    measurement = influx["measurement"]
    from_clause = f'"{measurement}"' if not rp else f'"{rp}"."{measurement}"'
    field = influx["field"]
    interval = influx.get("interval", "15m")

    q = (
        f'SELECT last("{field}") AS "kwh_total" '
        f"FROM {from_clause} "
        f"WHERE time >= '{to_rfc3339(start_utc)}' AND time < '{to_rfc3339(end_utc)}' "
        f'AND "entity_id"=\'{export_entity_id}\' '
        f"GROUP BY time({interval}) fill(null)"
    )

    try:
        data = influx_query(influx, q)
    except Exception as exc:
        logger.warning("Influx export query failed (date=%s start=%s end=%s): %s", date, start, end, exc)
        if cached:
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = True
            return cached
        raise
    series = data.get("results", [{}])[0].get("series", [])
    has_series = bool(series)
    values = series[0]["values"] if series else []

    points = []
    prev_total = None
    start_utc_ts = int(start_utc.timestamp())
    for ts, total in values:
        if total is None:
            kwh = None
        elif prev_total is None:
            kwh = total if ts == start_utc_ts else None
        else:
            diff = total - prev_total
            if diff >= 0:
                kwh = diff
            else:
                # Export counters can also restart within the day (e.g. inverter/session reset).
                kwh = total
        if total is not None:
            prev_total = total

        ts_dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        ts_local = ts_dt_utc.astimezone(tzinfo)
        points.append(
            {
                "time": ts_local.isoformat(),
                "time_utc": to_rfc3339(ts_dt_utc),
                "kwh_total": total,
                "kwh": kwh,
            }
        )

    result = {
        "range": {"start": to_rfc3339(start_utc), "end": to_rfc3339(end_utc)},
        "interval": interval,
        "entity_id": export_entity_id,
        "points": points,
        "tzinfo": tzinfo,
        "has_series": has_series,
        "from_cache": False,
        "cache_fallback": False,
    }
    if date and not start and not end and has_series:
        cache_payload = {
            "range": result["range"],
            "interval": result["interval"],
            "entity_id": result["entity_id"],
            "points": result["points"],
            "has_series": result["has_series"],
        }
        save_export_cache(date, cache_key, cache_payload)
    return result

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def save_config(new_config: dict = Body(...)):
    if isinstance(new_config, dict):
        new_config["price_provider"] = normalize_price_provider(new_config.get("price_provider"))
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_config, f, allow_unicode=True)
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(OPTIONS_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f)
    return {"status": "ok", "message": "Konfigurace uložena"}

@app.get("/api/fees-history")
def get_fees_history():
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    history = ensure_fee_history(cfg, tzinfo)
    history.sort(key=lambda x: x.get("effective_from", ""))
    return {"history": history}

@app.put("/api/fees-history")
def update_fees_history(payload: dict = Body(...)):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload.")
    history = payload.get("history")
    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="Invalid history payload.")

    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    today = datetime.now(tzinfo).date()

    normalized_entries = []
    seen_dates = set()
    for entry in history:
        if not isinstance(entry, dict):
            continue
        date_str = entry.get("effective_from")
        if not date_str:
            continue
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid effective_from: {date_str}")
        if date_str in seen_dates:
            raise HTTPException(status_code=400, detail=f"Duplicated effective_from: {date_str}")
        seen_dates.add(date_str)
        if date_obj > today:
            raise HTTPException(status_code=400, detail="effective_from cannot be in the future.")
        effective_to = entry.get("effective_to")
        effective_to_date = None
        if effective_to:
            try:
                effective_to_date = datetime.strptime(effective_to, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid effective_to: {effective_to}")
            if effective_to_date > today:
                raise HTTPException(status_code=400, detail="effective_to cannot be in the future.")
            if effective_to_date < date_obj:
                raise HTTPException(status_code=400, detail="effective_to must be >= effective_from.")
        snapshot = normalize_fee_snapshot(entry.get("snapshot", {}))
        normalized_entries.append(
            {
                "effective_from": date_str,
                "effective_to": effective_to,
                "from_date": date_obj,
                "to_date": effective_to_date,
                "snapshot": snapshot,
            }
        )

    if not normalized_entries:
        raise HTTPException(status_code=400, detail="History cannot be empty.")

    normalized_entries.sort(key=lambda x: x["from_date"])
    for idx, entry in enumerate(normalized_entries[:-1]):
        next_entry = normalized_entries[idx + 1]
        if entry["to_date"] is None:
            computed_to = next_entry["from_date"] - timedelta(days=1)
            if computed_to < entry["from_date"]:
                raise HTTPException(status_code=400, detail="effective_to must be >= effective_from.")
            entry["to_date"] = computed_to
            entry["effective_to"] = computed_to.strftime("%Y-%m-%d")
        if entry["to_date"] >= next_entry["from_date"]:
            raise HTTPException(status_code=400, detail="Fee history ranges overlap.")

    normalized = []
    for entry in normalized_entries:
        record = {"effective_from": entry["effective_from"], "snapshot": entry["snapshot"]}
        if entry["effective_to"]:
            record["effective_to"] = entry["effective_to"]
        normalized.append(record)
    save_fee_history(normalized)
    return {"history": normalized}

@app.get("/api/cache-status")
def get_cache_status():
    return cache_status()

@app.get("/api/version")
def get_version():
    return {"version": APP_VERSION}


# --- Spotové ceny ---
def get_spot_prices():
    # Nový endpoint s čtvrthodinovými daty
    url = "https://spotovaelektrina.cz/api/v1/price/get-prices-json-qh"
    logger.info("Fetching prices from API: %s", url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def calculate_final_price(price_spot_czk, hour, cfg, fee_snapshot):
    vt_periods = cfg.get("tarif", {}).get("vt_periods", [])
    is_vt = any(start <= hour < end for start, end in vt_periods)
    tarif_type = "VT" if is_vt else "NT"
    fees = fee_snapshot.get("kwh_fees", {})
    distribuce = fees.get("distribuce", {})
    subtotal = (
        price_spot_czk
        + fees.get("komodita_sluzba", 0)
        + fees.get("oze", 0)
        + fees.get("dan", 0)
        + fees.get("systemove_sluzby", 0)
        + distribuce.get(tarif_type, 0)
    )
    dph_multiplier = 1 + (fee_snapshot.get("dph_percent", 0) / 100.0)
    total = subtotal * dph_multiplier
    return round(total, 5)

@app.get("/api/prices")
def get_prices(date: str = Query(default=None)):
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    if date:
        return {"prices": get_prices_for_date(cfg, date, tzinfo)}
    final_list = []
    today_str = datetime.now(tzinfo).strftime("%Y-%m-%d")
    final_list.extend(get_prices_for_date(cfg, today_str, tzinfo, include_neighbor_live=True))
    tomorrow_str = (datetime.now(tzinfo) + timedelta(days=1)).strftime("%Y-%m-%d")
    final_list.extend(get_prices_for_date(cfg, tomorrow_str, tzinfo))
    return {"prices": final_list}

@app.post("/api/prices/refresh")
def refresh_prices(payload: dict = Body(default=None)):
    payload = payload or {}
    cfg = load_config()
    provider = get_price_provider(cfg)
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))

    dates_to_refresh = []
    requested_date = payload.get("date")
    if requested_date:
        try:
            datetime.strptime(str(requested_date), "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc
        dates_to_refresh.append(str(requested_date))
    else:
        today_str = datetime.now(tzinfo).strftime("%Y-%m-%d")
        tomorrow_str = (datetime.now(tzinfo) + timedelta(days=1)).strftime("%Y-%m-%d")
        dates_to_refresh.extend([today_str, tomorrow_str])

    refreshed = []
    for date_str in dates_to_refresh:
        clear_prices_cache_for_date(date_str, remove_files=False)
        entries = get_prices_for_date(cfg, date_str, tzinfo, force_refresh=True)
        refreshed.append(
            {
                "date": date_str,
                "count": len(entries),
                "has_data": bool(entries),
            }
        )

    return {
        "status": "ok",
        "provider": provider,
        "refreshed": refreshed,
    }

@app.get("/api/consumption")
def get_consumption(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    cfg = load_config()
    result = get_consumption_points(cfg, date, start, end)
    return {
        "range": result["range"],
        "interval": result["interval"],
        "entity_id": result["entity_id"],
        "points": result["points"],
        "from_cache": result.get("from_cache", False),
        "cache_fallback": result.get("cache_fallback", False),
    }

@app.get("/api/costs")
def get_costs(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    cfg = load_config()
    consumption = get_consumption_points(cfg, date, start, end)
    tzinfo = consumption["tzinfo"]
    if not consumption.get("has_series", False):
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                if date_obj <= datetime.now(tzinfo).date():
                    raise HTTPException(
                        status_code=500,
                        detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
                    )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        else:
            range_end = datetime.fromisoformat(consumption["range"]["end"].replace("Z", "+00:00"))
            if range_end <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=500,
                    detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
                )
    if date:
        price_map, price_map_utc = build_price_map_for_date(cfg, date, tzinfo)
    else:
        start_dt = datetime.fromisoformat(consumption["range"]["start"].replace("Z", "+00:00"))
        date_str = start_dt.astimezone(tzinfo).strftime("%Y-%m-%d")
        price_map, price_map_utc = build_price_map_for_date(cfg, date_str, tzinfo)

    points = []
    total_kwh = 0.0
    total_cost = 0.0
    for entry in consumption["points"]:
        kwh = entry["kwh"]
        time_local = datetime.fromisoformat(entry["time"])
        key = time_local.strftime("%Y-%m-%d %H:%M")
        price = price_map.get(key)
        if price is None:
            time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
            key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
            price = price_map_utc.get(key_utc)
        final_price = price["final"] if price else None
        cost = None
        if kwh is not None and final_price is not None:
            cost = round(kwh * final_price, 5)
            total_kwh += kwh
            total_cost += cost

        points.append(
            {
                "time": entry["time"],
                "time_utc": entry["time_utc"],
                "kwh": kwh,
                "final_price": final_price,
                "cost": cost,
            }
        )

    return {
        "range": consumption["range"],
        "interval": consumption["interval"],
        "entity_id": consumption["entity_id"],
        "summary": {
            "kwh_total": round(total_kwh, 5),
            "cost_total": round(total_cost, 5),
        },
        "points": points,
        "from_cache": consumption.get("from_cache", False),
        "cache_fallback": consumption.get("cache_fallback", False),
    }

@app.get("/api/export")
def get_export(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    cfg = load_config()
    export = get_export_points(cfg, date, start, end)
    tzinfo = export["tzinfo"]
    if not export.get("has_series", False):
        if date:
            try:
                date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                if date_obj <= datetime.now(tzinfo).date():
                    raise HTTPException(
                        status_code=500,
                        detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj export entity_id.",
                    )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
        else:
            range_end = datetime.fromisoformat(export["range"]["end"].replace("Z", "+00:00"))
            if range_end <= datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=500,
                    detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj export entity_id.",
                )
    if date:
        price_map, price_map_utc = build_price_map_for_date(cfg, date, tzinfo)
    else:
        start_dt = datetime.fromisoformat(export["range"]["start"].replace("Z", "+00:00"))
        date_str = start_dt.astimezone(tzinfo).strftime("%Y-%m-%d")
        price_map, price_map_utc = build_price_map_for_date(cfg, date_str, tzinfo)

    coef_by_date = {}
    points = []
    total_kwh = 0.0
    total_sell = 0.0
    for entry in export["points"]:
        kwh = entry["kwh"]
        time_local = datetime.fromisoformat(entry["time"])
        key = time_local.strftime("%Y-%m-%d %H:%M")
        price = price_map.get(key)
        if price is None:
            time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
            key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
            price = price_map_utc.get(key_utc)
        spot_price = price["spot"] if price else None
        date_key = time_local.strftime("%Y-%m-%d")
        coef_kwh = coef_by_date.get(date_key)
        if coef_kwh is None:
            fee_snapshot = get_fee_snapshot_for_date(cfg, date_key, tzinfo)
            coef_kwh = get_sell_coefficient_kwh(cfg, fee_snapshot)
            coef_by_date[date_key] = coef_kwh
        sell_price = spot_price - coef_kwh if spot_price is not None else None
        sell = None
        if kwh is not None and sell_price is not None:
            sell = round(kwh * sell_price, 5)
            total_kwh += kwh
            total_sell += sell

        points.append(
            {
                "time": entry["time"],
                "time_utc": entry["time_utc"],
                "kwh": kwh,
                "spot_price": spot_price,
                "sell_price": round(sell_price, 5) if sell_price is not None else None,
                "sell": sell,
            }
        )

    return {
        "range": export["range"],
        "interval": export["interval"],
        "entity_id": export["entity_id"],
        "summary": {
            "export_kwh_total": round(total_kwh, 5),
            "sell_total": round(total_sell, 5),
        },
        "points": points,
        "from_cache": export.get("from_cache", False),
        "cache_fallback": export.get("cache_fallback", False),
    }


@app.get("/api/schedule")
def get_schedule(
    duration: int = Query(default=120, ge=1, le=360),
    count: int = Query(default=3, ge=1, le=3),
):
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    now = datetime.now(tzinfo)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    duration = max(1, min(360, duration))

    def next_slot(dt):
        minute = (dt.minute // 15 + (1 if dt.minute % 15 else 0)) * 15
        if minute == 60:
            return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return dt.replace(minute=minute, second=0, microsecond=0)

    min_start = next_slot(now)
    slots = int((duration + 14) // 15)
    candidates = []

    for date_obj in (today, tomorrow):
        date_str = date_obj.strftime("%Y-%m-%d")
        entries = get_prices_for_date(cfg, date_str, tzinfo)
        if not entries:
            continue
        entries_sorted = sorted(entries, key=lambda x: x["time"])
        if len(entries_sorted) < slots:
            continue
        for i in range(0, len(entries_sorted) - slots + 1):
            window = entries_sorted[i:i + slots]
            window_start = datetime.strptime(window[0]["time"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
            if date_obj == today and window_start < min_start:
                continue
            avg_price = sum(p["final"] for p in window) / slots
            energy_kwh = duration / 60.0
            total_cost = avg_price * energy_kwh
            end_dt = window_start + timedelta(minutes=duration)
            candidates.append({
                "start": window[0]["time"],
                "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                "avg_price": round(avg_price, 5),
                "energy_kwh": round(energy_kwh, 3),
                "total_cost": round(total_cost, 5),
            })

    if not candidates:
        return {"duration": duration, "recommendations": [], "note": "Data nejsou k dispozici."}

    candidates.sort(key=lambda x: (x["avg_price"], x["start"]))
    results = []
    for item in candidates:
        start_dt = datetime.strptime(item["start"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
        if all(abs((start_dt - datetime.strptime(r["start"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)).total_seconds()) >= duration * 60 for r in results):
            results.append(item)
        if len(results) >= count:
            break

    return {
        "duration": duration,
        "recommendations": results,
        "note": None,
    }

@app.get("/api/daily-summary")
def get_daily_summary(month: str = Query(...)):
    if not re.match(r"^\d{4}-\d{2}$", month):
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    year, month_num = map(int, month.split("-"))
    start = datetime(year, month_num, 1)
    if month_num == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month_num + 1, 1)
    today = datetime.now(tzinfo).date()

    days = []
    current = start
    total_kwh = 0.0
    total_cost = 0.0
    total_export_kwh = 0.0
    total_sell = 0.0
    any_series = False
    any_export_series = False
    while current < next_month and current.date() <= today:
        date_str = current.strftime("%Y-%m-%d")
        totals = calculate_daily_totals(cfg, date_str)
        export_totals = calculate_daily_export_totals(cfg, date_str)
        if totals.get("has_series"):
            any_series = True
        if export_totals.get("has_series"):
            any_export_series = True
        days.append(
            {
                "date": date_str,
                "kwh_total": totals["kwh_total"],
                "cost_total": totals["cost_total"],
                "export_kwh_total": export_totals["export_kwh_total"],
                "sell_total": export_totals["sell_total"],
            }
        )
        if totals["kwh_total"] is not None:
            total_kwh += totals["kwh_total"]
        if totals["cost_total"] is not None:
            total_cost += totals["cost_total"]
        if export_totals["export_kwh_total"] is not None:
            total_export_kwh += export_totals["export_kwh_total"]
        if export_totals["sell_total"] is not None:
            total_sell += export_totals["sell_total"]
        current += timedelta(days=1)

    if not any_series and start.date() <= today:
        raise HTTPException(
            status_code=500,
            detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
        )

    return {
        "month": month,
        "days": days,
        "summary": {
            "kwh_total": round(total_kwh, 5),
            "cost_total": round(total_cost, 5),
            "export_kwh_total": round(total_export_kwh, 5) if any_export_series else None,
            "sell_total": round(total_sell, 5) if any_export_series else None,
        },
    }

@app.get("/api/billing-month")
def get_billing_month(month: str = Query(...)):
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    return compute_monthly_billing(cfg, month, tzinfo)

@app.get("/api/billing-year")
def get_billing_year(year: int = Query(..., ge=2000, le=2100)):
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    now = datetime.now(tzinfo)
    current_year = now.year
    current_month = now.month
    if year > current_year:
        return {"year": year, "months": [], "totals": {"actual": {}, "projected": {}}}

    end_month = 12 if year < current_year else current_month
    months = []
    totals_actual_var = 0.0
    totals_actual_fixed = 0.0
    totals_actual_total = 0.0
    totals_actual_net = 0.0
    totals_projected_var = 0.0
    totals_projected_fixed = 0.0
    totals_projected_total = 0.0
    totals_projected_net = 0.0

    for month_num in range(1, end_month + 1):
        month_str = f"{year}-{month_num:02d}"
        data = compute_monthly_billing(cfg, month_str, tzinfo, require_data=False)
        months.append(
            {
                "month": data["month"],
                "days_in_month": data["days_in_month"],
                "days_with_data": data["days_with_data"],
                "actual": data["actual"],
                "projected": data["projected"],
            }
        )
        if data["days_with_data"] > 0:
            totals_actual_var += data["actual"]["variable_cost"]
            totals_actual_fixed += data["actual"]["fixed_cost"]
            totals_actual_total += data["actual"]["total_cost"]
            if data["actual"].get("net_total") is not None:
                totals_actual_net += data["actual"]["net_total"]
            totals_projected_var += data["projected"]["variable_cost"]
            totals_projected_fixed += data["projected"]["fixed_cost"]
            totals_projected_total += data["projected"]["total_cost"]
            if data["projected"].get("net_total") is not None:
                totals_projected_net += data["projected"]["net_total"]

    totals = {
        "actual": {
            "variable_cost": round(totals_actual_var, 5),
            "fixed_cost": round(totals_actual_fixed, 5),
            "total_cost": round(totals_actual_total, 5),
            "net_total": round(totals_actual_net, 5),
        },
        "projected": {
            "variable_cost": round(totals_projected_var, 5),
            "fixed_cost": round(totals_projected_fixed, 5),
            "total_cost": round(totals_projected_total, 5),
            "net_total": round(totals_projected_net, 5),
        },
    }

    return {"year": year, "months": months, "totals": totals}



def schedule_prefetch_loop():
    while True:
        cfg = load_config()
        provider = get_price_provider(cfg)
        tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
        now = datetime.now(tzinfo)
        tomorrow = now.date() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        target_today = datetime.combine(now.date(), datetime_time(13, 5), tzinfo)
        next_run = None

        if has_price_cache(tomorrow_str, provider=provider):
            logger.info("Tomorrow prices already cached (%s); next check tomorrow.", tomorrow_str)
            next_run = datetime.combine(now.date() + timedelta(days=1), datetime_time(13, 5), tzinfo)
        else:
            if now < target_today:
                next_run = target_today
            else:
                try:
                    get_prices_for_date(cfg, tomorrow_str, tzinfo)
                except Exception as exc:
                    logger.warning("Prefetch failed for %s: %s", tomorrow_str, exc)
                if has_price_cache(tomorrow_str, provider=provider):
                    next_run = datetime.combine(now.date() + timedelta(days=1), datetime_time(13, 5), tzinfo)
                else:
                    next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)

        sleep_seconds = max(30, (next_run - datetime.now(tzinfo)).total_seconds())
        time_module.sleep(sleep_seconds)


# --- Startup logging ---
@app.on_event("startup")
def log_cache_status():

    thread = threading.Thread(target=schedule_prefetch_loop, daemon=True)
    thread.start()
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    status = cache_status()
    prices_status = status.get("prices", {})
    consumption_status = status.get("consumption", {})
    logger.info(
        "Prices cache status: dir=%s count=%s latest=%s size_bytes=%s",
        prices_status.get("dir"),
        prices_status.get("count"),
        prices_status.get("latest"),
        prices_status.get("size_bytes"),
    )
    logger.info(
        "Consumption cache status: dir=%s count=%s latest=%s size_bytes=%s",
        consumption_status.get("dir"),
        consumption_status.get("count"),
        consumption_status.get("latest"),
        consumption_status.get("size_bytes"),
    )

# --- Frontend React Build ---
build_path = Path(__file__).parent / "frontend_build"

if build_path.exists():
    # Servíruj statiku (JS, CSS, obrázky)
    app.mount("/static", StaticFiles(directory=build_path / "static"), name="static")

    # Manifest a favicon
    @app.get("/site.webmanifest")
    def manifest():
        return FileResponse(build_path / "site.webmanifest")

    @app.get("/favicon.ico")
    def favicon():
        return FileResponse(build_path / "favicon.ico")
        
    @app.get("/android-chrome-192x192.png")
    def favicon192():
        return FileResponse(build_path / "android-chrome-192x192.png")

    @app.get("/android-chrome-512x512.png")
    def favicon512():
        return FileResponse(build_path / "android-chrome-512x512.png")

    # Catch-all pro React routing
    @app.get("/{full_path:path}")
    def serve_react(full_path: str):
        return FileResponse(build_path / "index.html")
