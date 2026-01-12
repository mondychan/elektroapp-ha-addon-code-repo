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
from datetime import datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo
from pathlib import Path
import logging

app = FastAPI(title="Elektroapp API")

CONFIG_FILE = "config.yaml"
HA_OPTIONS_FILE = Path("/data/options.json")
CONFIG_DIR = Path("/config")
STORAGE_DIR = Path(os.getenv("ELEKTROAPP_STORAGE", ""))
if not STORAGE_DIR:
    if CONFIG_DIR.exists():
        STORAGE_DIR = CONFIG_DIR / "elektroapp"
    else:
        STORAGE_DIR = Path("/data")
PRICES_CACHE = {}
DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
CACHE_DIR = (STORAGE_DIR / "prices-cache") if STORAGE_DIR.exists() else (Path(__file__).parent / "cache")
OPTIONS_BACKUP_FILE = STORAGE_DIR / "options.json"
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
        tarif = cfg.get("tarif")
        if isinstance(tarif, dict):
            vt_periods = tarif.get("vt_periods")
            if isinstance(vt_periods, str):
                tarif["vt_periods"] = parse_vt_periods(vt_periods)
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
    path = CACHE_DIR / f"prices-{date_str}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def save_prices_cache(date_str, entries):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"prices-{date_str}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    logger.info("Saved prices cache for %s to %s", date_str, path)


def has_price_cache(date_str):
    cached = load_prices_cache(date_str)
    return bool(cached)

def cache_status():
    if not CACHE_DIR.exists():
        return {"dir": str(CACHE_DIR), "count": 0, "latest": None, "size_bytes": 0}
    files = sorted(CACHE_DIR.glob("prices-*.json"))
    latest = None
    total_size = 0
    if files:
        latest = files[-1].stem.replace("prices-", "")
        total_size = sum(path.stat().st_size for path in files)
    return {"dir": str(CACHE_DIR), "count": len(files), "latest": latest, "size_bytes": total_size}

def build_entries_from_api(cfg, date_str, hours):
    entries = []
    for entry in hours:
        hour = entry["hour"]
        minute = entry.get("minute", 0)
        spot_kwh = entry["priceCZK"] / 1000
        final_price = calculate_final_price(spot_kwh, hour, cfg)
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

def get_prices_for_date(cfg, date_str, tzinfo):
    if date_str in PRICES_CACHE:
        return PRICES_CACHE[date_str]
    cached = load_prices_cache(date_str)
    if cached is not None:
        PRICES_CACHE[date_str] = cached
        logger.info("Prices cache hit for %s", date_str)
        return cached
    logger.info("Prices cache miss for %s", date_str)

    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now(tzinfo).date()
    tomorrow = today + timedelta(days=1)

    entries = []
    if date_obj in (today, tomorrow):
        data = get_spot_prices()
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        today_entries = build_entries_from_api(cfg, today_str, data.get("hoursToday", []))
        tomorrow_entries = build_entries_from_api(cfg, tomorrow_str, data.get("hoursTomorrow", []))
        if today_entries:
            PRICES_CACHE[today_str] = today_entries
            save_prices_cache(today_str, today_entries)
        if tomorrow_entries:
            PRICES_CACHE[tomorrow_str] = tomorrow_entries
            save_prices_cache(tomorrow_str, tomorrow_entries)
        entries = today_entries if date_obj == today else tomorrow_entries
        return entries
    else:
        logger.info("Fetching historical prices from HTML for %s", date_str)
        url = f"https://spotovaelektrina.cz/denni-ceny/{date_str}"
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        rows = parse_price_html(r.text)
        for time_str, price_czk in rows:
            hour, minute = map(int, time_str.split(":"))
            spot_kwh = price_czk / 1000
            final_price = calculate_final_price(spot_kwh, hour, cfg)
            entries.append(
                {
                    "time": f"{date_str} {hour:02d}:{minute:02d}",
                    "hour": hour,
                    "minute": minute,
                    "spot": round(spot_kwh, 5),
                    "final": final_price,
                }
            )

    PRICES_CACHE[date_str] = entries
    save_prices_cache(date_str, entries)
    return entries

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
        return {"kwh_total": None, "cost_total": None}
    return {"kwh_total": round(total_kwh, 5), "cost_total": round(total_cost, 5)}

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

def calculate_final_price(price_spot_czk, hour, cfg):
    vt_periods = cfg.get("tarif", {}).get("vt_periods", [])
    is_vt = any(start <= hour < end for start, end in vt_periods)
    tarif_type = "VT" if is_vt else "NT"

    komodita = (price_spot_czk + cfg.get("poplatky", {}).get("komodita_sluzba", 0)) * cfg.get("dph", 1)
    poze = cfg.get("poplatky", {}).get("poze", 0)
    dan = cfg.get("poplatky", {}).get("dan", 0)
    distribuce = cfg.get("poplatky", {}).get("distribuce", {}).get(tarif_type, 0)

    total = komodita + poze + dan + distribuce
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
    duration: int = Query(default=120, ge=15, le=1440),
    count: int = Query(default=3, ge=1, le=3),
):
    cfg = load_config()
    tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    now = datetime.now(tzinfo)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    if duration % 15 != 0:
        duration = int(((duration + 14) // 15) * 15)

    def next_slot(dt):
        minute = (dt.minute // 15 + (1 if dt.minute % 15 else 0)) * 15
        if minute == 60:
            return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        return dt.replace(minute=minute, second=0, microsecond=0)

    min_start = next_slot(now)
    slots = duration // 15
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
            energy_kwh = slots * 0.25
            total_cost = avg_price * energy_kwh
            candidates.append({
                "start": window[0]["time"],
                "end": window[-1]["time"],
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
    while current < next_month and current.date() <= today:
        date_str = current.strftime("%Y-%m-%d")
        totals = calculate_daily_totals(cfg, date_str)
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

    return {
        "month": month,
        "days": days,
        "summary": {
            "kwh_total": round(total_kwh, 5),
            "cost_total": round(total_cost, 5),
        },
    }



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
