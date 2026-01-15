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
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = (STORAGE_DIR / "prices-cache") if STORAGE_DIR else (Path(__file__).parent / "cache")
OPTIONS_BACKUP_FILE = STORAGE_DIR / "options.json"
FEES_HISTORY_FILE = STORAGE_DIR / "fees-history.json"
APP_VERSION = os.getenv("ADDON_VERSION", os.getenv("APP_VERSION", "dev"))
logger = logging.getLogger("uvicorn.error")

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

def ensure_fee_history(cfg, tzinfo):
    history = load_fee_history()
    history.sort(key=lambda x: x.get("effective_from", ""))
    today_str = datetime.now(tzinfo).strftime("%Y-%m-%d")
    snapshot = build_fee_snapshot(cfg)
    if not history:
        history = [{"effective_from": today_str, "snapshot": snapshot}]
        save_fee_history(history)
        return history
    last = history[-1]
    if last.get("snapshot") != snapshot:
        if last.get("effective_from") == today_str:
            last["snapshot"] = snapshot
        else:
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
    for record in history:
        try:
            record_date = datetime.strptime(record.get("effective_from", ""), "%Y-%m-%d").date()
        except ValueError:
            continue
        if record_date <= target_date:
            candidate = record
        else:
            break
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
        start_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tzinfo)
        end_local = start_local + timedelta(days=1)
    elif start_str and end_str:
        start_local = datetime.fromisoformat(start_str)
        end_local = datetime.fromisoformat(end_str)
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

def load_prices_cache(date_str):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"prices-{date_str}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_prices_cache(date_str, entries):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"prices-{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    logger.info("Saved prices cache for %s to %s", date_str, path)


def has_price_cache(date_str):
    cached = load_prices_cache(date_str)
    return bool(cached)

def cache_status():
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if not CACHE_DIR.exists():
        return {"dir": str(CACHE_DIR), "count": 0, "latest": None, "size_bytes": 0}
    files = sorted(CACHE_DIR.glob("prices-*.json"))
    latest = None
    total_size = 0
    if files:
        latest = files[-1].stem.replace("prices-", "")
        total_size = sum(path.stat().st_size for path in files)
    return {"dir": str(CACHE_DIR), "count": len(files), "latest": latest, "size_bytes": total_size}

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

def get_prices_for_date(cfg, date_str, tzinfo):
    fee_snapshot = get_fee_snapshot_for_date(cfg, date_str, tzinfo)
    cached = PRICES_CACHE.get(date_str)
    if cached:
        return apply_fee_snapshot(cached, cfg, fee_snapshot)
    cached = load_prices_cache(date_str)
    if cached:
        PRICES_CACHE[date_str] = cached
        logger.info("Prices cache hit for %s", date_str)
        return apply_fee_snapshot(cached, cfg, fee_snapshot)
    logger.info("Prices cache miss for %s", date_str)

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now(tzinfo).date()
    tomorrow = today + timedelta(days=1)

    entries = []
    if date_obj in (today, tomorrow):
        data = get_spot_prices()
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        today_snapshot = get_fee_snapshot_for_date(cfg, today_str, tzinfo)
        tomorrow_snapshot = get_fee_snapshot_for_date(cfg, tomorrow_str, tzinfo)
        today_entries = build_entries_from_api(cfg, today_str, data.get("hoursToday", []), today_snapshot)
        tomorrow_entries = build_entries_from_api(cfg, tomorrow_str, data.get("hoursTomorrow", []), tomorrow_snapshot)
        if today_entries:
            PRICES_CACHE[today_str] = today_entries
            save_prices_cache(today_str, today_entries)
        if tomorrow_entries:
            PRICES_CACHE[tomorrow_str] = tomorrow_entries
            save_prices_cache(tomorrow_str, tomorrow_entries)
        entries = today_entries if date_obj == today else tomorrow_entries
    else:
        logger.info("Fetching historical prices from HTML for %s", date_str)
        url = f"https://spotovaelektrina.cz/denni-ceny/{date_str}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rows = parse_price_html(r.text)
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

    if entries:
        PRICES_CACHE[date_str] = entries
        save_prices_cache(date_str, entries)
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

def compute_monthly_billing(cfg, month_str, tzinfo):
    if not re.match(r"^\d{4}-\d{2}$", month_str):
        raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
    year, month_num = map(int, month_str.split("-"))
    days_in_month = calendar.monthrange(year, month_num)[1]
    start_date = datetime(year, month_num, 1).date()
    today = datetime.now(tzinfo).date()

    actual_variable = 0.0
    actual_kwh = 0.0
    days_with_data = 0
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

    if days_with_data == 0 and start_date <= today:
        raise HTTPException(
            status_code=500,
            detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
        )

    projected_variable = 0.0
    if days_with_data > 0:
        projected_variable = (actual_variable / days_with_data) * days_in_month

    actual = {
        "kwh_total": round(actual_kwh, 5) if days_with_data else None,
        "variable_cost": round(actual_variable, 5),
        "fixed_cost": round(fixed_total, 5),
        "total_cost": round(actual_variable + fixed_total, 5),
    }
    projected = {
        "variable_cost": round(projected_variable, 5),
        "fixed_cost": round(fixed_total, 5),
        "total_cost": round(projected_variable + fixed_total, 5),
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

    data = influx_query(influx, q)
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
            kwh = diff if diff >= 0 else None
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

    return {
        "range": {"start": to_rfc3339(start_utc), "end": to_rfc3339(end_utc)},
        "interval": interval,
        "entity_id": entity_id,
        "points": points,
        "tzinfo": tzinfo,
        "has_series": has_series,
    }

@app.get("/api/config")
def get_config():
    return load_config()

@app.post("/api/config")
def save_config(new_config: dict = Body(...)):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_config, f, allow_unicode=True)
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(OPTIONS_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f)
    return {"status": "ok", "message": "Konfigurace uložena"}

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
    final_list.extend(get_prices_for_date(cfg, today_str, tzinfo))
    tomorrow_str = (datetime.now(tzinfo) + timedelta(days=1)).strftime("%Y-%m-%d")
    final_list.extend(get_prices_for_date(cfg, tomorrow_str, tzinfo))
    return {"prices": final_list}

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
    any_series = False
    while current < next_month and current.date() <= today:
        date_str = current.strftime("%Y-%m-%d")
        totals = calculate_daily_totals(cfg, date_str)
        if totals.get("has_series"):
            any_series = True
        days.append(
            {
                "date": date_str,
                "kwh_total": totals["kwh_total"],
                "cost_total": totals["cost_total"],
            }
        )
        if totals["kwh_total"] is not None:
            total_kwh += totals["kwh_total"]
        if totals["cost_total"] is not None:
            total_cost += totals["cost_total"]
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
    totals_projected_var = 0.0
    totals_projected_fixed = 0.0
    totals_projected_total = 0.0

    for month_num in range(1, end_month + 1):
        month_str = f"{year}-{month_num:02d}"
        data = compute_monthly_billing(cfg, month_str, tzinfo)
        months.append(
            {
                "month": data["month"],
                "days_in_month": data["days_in_month"],
                "days_with_data": data["days_with_data"],
                "actual": data["actual"],
                "projected": data["projected"],
            }
        )
        totals_actual_var += data["actual"]["variable_cost"]
        totals_actual_fixed += data["actual"]["fixed_cost"]
        totals_actual_total += data["actual"]["total_cost"]
        totals_projected_var += data["projected"]["variable_cost"]
        totals_projected_fixed += data["projected"]["fixed_cost"]
        totals_projected_total += data["projected"]["total_cost"]

    totals = {
        "actual": {
            "variable_cost": round(totals_actual_var, 5),
            "fixed_cost": round(totals_actual_fixed, 5),
            "total_cost": round(totals_actual_total, 5),
        },
        "projected": {
            "variable_cost": round(totals_projected_var, 5),
            "fixed_cost": round(totals_projected_fixed, 5),
            "total_cost": round(totals_projected_total, 5),
        },
    }

    return {"year": year, "months": months, "totals": totals}



def schedule_prefetch_loop():
    while True:
        cfg = load_config()
        tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
        now = datetime.now(tzinfo)
        tomorrow = now.date() + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        target_today = datetime.combine(now.date(), datetime_time(13, 5), tzinfo)
        next_run = None

        if has_price_cache(tomorrow_str):
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
                if has_price_cache(tomorrow_str):
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
    logger.info(
        "Prices cache status: dir=%s count=%s latest=%s size_bytes=%s",
        status["dir"],
        status["count"],
        status["latest"],
        status["size_bytes"],
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
