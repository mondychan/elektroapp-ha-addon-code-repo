from fastapi import Body, HTTPException, Query
from api import get_local_tz, parse_time_range, to_rfc3339
from battery import average_recent_power, build_slot_avg_profile, get_slot_index_for_dt
from billing import compute_fixed_breakdown_for_day
from cache import is_cache_fresh, is_date_cache_complete, is_today_date, should_use_daily_cache
from influx import parse_influx_interval_to_minutes
from services.battery_service import BatteryService
from services.billing_service import BillingService
from services.costs_service import CostsService
from services.export_service import ExportService
from services.influx_service import InfluxService
from services.insights_service import InsightsService
from services.prices_service import PricesService
from services.runtime_state import RuntimeState
from services.schedule_service import ScheduleService
from pricing import (
    DEFAULT_PRICE_PROVIDER,
    PRICE_PROVIDER_OTE,
    PRICE_PROVIDER_SPOT,
    _safe_float,
    build_fee_snapshot,
    calculate_final_price,
    get_price_provider,
    normalize_dph_percent,
    normalize_fee_snapshot,
    normalize_price_provider,
    parse_price_html,
    parse_vt_periods,
)
import requests
import yaml
import os
import json
import threading
import atexit
import time as time_module
import re
import xml.etree.ElementTree as ET
from datetime import date as datetime_date, datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo
from pathlib import Path
import logging
from requests import RequestException
from typing import Any

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
SERIES_CACHE_TTL_SECONDS = 600
CONSUMPTION_CACHE_TTL_SECONDS = SERIES_CACHE_TTL_SECONDS
EXPORT_CACHE_DIR = (
    STORAGE_DIR / "export-cache" if STORAGE_DIR else (Path(__file__).parent / "export-cache")
)
EXPORT_CACHE_TTL_SECONDS = SERIES_CACHE_TTL_SECONDS
SERIES_CACHE_KEY_VERSION = 2
OPTIONS_BACKUP_FILE = STORAGE_DIR / "options.json"
FEES_HISTORY_FILE = STORAGE_DIR / "fees-history.json"
APP_VERSION = os.getenv("ADDON_VERSION", os.getenv("APP_VERSION", "dev"))
logger = logging.getLogger("uvicorn.error")
INFLUX_SERVICE = InfluxService(logger=logger)
RUNTIME_STATE = RuntimeState()
PREFETCH_LOCK_STALE_SECONDS = 48 * 3600

OTE_PUBLIC_URL = "https://www.ote-cr.cz/services/PublicDataService"
OTE_PUBLIC_URL_HTTP = "http://www.ote-cr.cz/services/PublicDataService"
OTE_SOAP_ACTION_GET_DAM_PRICE_PERIOD_E = "http://www.ote-cr.cz/schema/service/public/GetDamPricePeriodE"
CNB_RATES_URL = "https://api.cnb.cz/cnbapi/exrates/daily"
OTE_PUBLIC_NS = "{http://www.ote-cr.cz/schema/service/public}"
SOAP_FAULT_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"
PRAGUE_TZ = ZoneInfo("Europe/Prague")
OTE_FAILURE_RETRY_SECONDS = 600

# --- Konfigurace ---

def mark_ote_unavailable(reason):
    RUNTIME_STATE.mark_ote_unavailable(OTE_FAILURE_RETRY_SECONDS)
    logger.warning("OTE marked unavailable for %ss: %s", OTE_FAILURE_RETRY_SECONDS, reason)

def get_ote_backoff_remaining_seconds():
    return RUNTIME_STATE.get_ote_backoff_remaining_seconds()

def is_ote_unavailable():
    return RUNTIME_STATE.is_ote_unavailable()

def utc_now_iso_z():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

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

def load_fee_history():
    if not FEES_HISTORY_FILE.exists():
        return []
    try:
        with open(FEES_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError, TypeError):
        return []

def save_fee_history(history):
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    with open(FEES_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f)

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
        except (OSError, json.JSONDecodeError, TypeError):
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


def resolve_config_and_timezone(cfg=None, tzinfo=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    tzinfo = tzinfo or get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    return cfg, tzinfo

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

def get_battery_cfg(cfg):
    battery = cfg.get("battery", {}) if isinstance(cfg.get("battery"), dict) else {}
    return {
        "enabled": bool(battery.get("enabled", False)),
        "soc_entity_id": battery.get("soc_entity_id"),
        "power_entity_id": battery.get("power_entity_id"),
        "input_energy_today_entity_id": battery.get("input_energy_today_entity_id"),
        "output_energy_today_entity_id": battery.get("output_energy_today_entity_id"),
        "usable_capacity_kwh": _safe_float(battery.get("usable_capacity_kwh", 0)),
        "reserve_soc_percent": _safe_float(battery.get("reserve_soc_percent", 15)),
        "eta_smoothing_minutes": max(1, int(_safe_float(battery.get("eta_smoothing_minutes", 15)) or 15)),
        "min_power_threshold_w": max(0.0, _safe_float(battery.get("min_power_threshold_w", 150))),
        "charge_efficiency": _safe_float(battery.get("charge_efficiency", 0.95)) or 0.95,
        "discharge_efficiency": _safe_float(battery.get("discharge_efficiency", 0.95)) or 0.95,
    }

def get_energy_entities_cfg(cfg):
    energy = cfg.get("energy", {}) if isinstance(cfg.get("energy"), dict) else {}
    return {
        "house_load_power_entity_id": energy.get("house_load_power_entity_id"),
        "grid_import_power_entity_id": energy.get("grid_import_power_entity_id"),
        "grid_export_power_entity_id": energy.get("grid_export_power_entity_id"),
        "pv_power_total_entity_id": energy.get("pv_power_total_entity_id"),
        "pv_power_1_entity_id": energy.get("pv_power_1_entity_id"),
        "pv_power_2_entity_id": energy.get("pv_power_2_entity_id"),
    }

def get_forecast_solar_cfg(cfg):
    forecast = cfg.get("forecast_solar", {}) if isinstance(cfg.get("forecast_solar"), dict) else {}
    return {
        "enabled": bool(forecast.get("enabled", False)),
        "power_now_entity_id": forecast.get("power_now_entity_id"),
        "energy_current_hour_entity_id": forecast.get("energy_current_hour_entity_id"),
        "energy_next_hour_entity_id": forecast.get("energy_next_hour_entity_id"),
        "energy_production_today_entity_id": forecast.get("energy_production_today_entity_id"),
        "energy_production_today_remaining_entity_id": forecast.get("energy_production_today_remaining_entity_id"),
        "energy_production_tomorrow_entity_id": forecast.get("energy_production_tomorrow_entity_id"),
        "power_highest_peak_time_today_entity_id": forecast.get("power_highest_peak_time_today_entity_id"),
        "power_highest_peak_time_tomorrow_entity_id": forecast.get("power_highest_peak_time_tomorrow_entity_id"),
    }

def has_battery_required_cfg(battery_cfg):
    return bool(
        battery_cfg.get("soc_entity_id")
        and battery_cfg.get("power_entity_id")
        and battery_cfg.get("usable_capacity_kwh", 0) > 0
    )

def get_sell_coefficient_kwh(cfg, fee_snapshot=None):
    prodej = None
    if isinstance(fee_snapshot, dict):
        prodej = fee_snapshot.get("prodej") if isinstance(fee_snapshot.get("prodej"), dict) else None
    if not isinstance(prodej, dict):
        prodej = cfg.get("prodej", {}) if isinstance(cfg.get("prodej"), dict) else {}
    coef_mwh = _safe_float(prodej.get("koeficient_snizeni_ceny", 0))
    return coef_mwh / 1000.0

def influx_query(influx, query):
    return INFLUX_SERVICE.influx_query(influx, query)

def get_measurement_candidates(influx, preferred=None):
    return INFLUX_SERVICE.get_measurement_candidates(influx, preferred=preferred)

def get_entity_id_candidates(entity_id):
    return INFLUX_SERVICE.get_entity_id_candidates(entity_id)

def query_entity_series(
    influx,
    entity_id,
    start_utc,
    end_utc,
    interval="15m",
    tzinfo=None,
    numeric=True,
    measurement_candidates=None,
):
    return INFLUX_SERVICE.query_entity_series(
        influx,
        entity_id,
        start_utc,
        end_utc,
        interval=interval,
        tzinfo=tzinfo,
        numeric=numeric,
        measurement_candidates=measurement_candidates,
    )

def query_entity_last_value(
    influx,
    entity_id,
    tzinfo=None,
    lookback_hours=72,
    numeric=True,
    measurement_candidates=None,
):
    return INFLUX_SERVICE.query_entity_last_value(
        influx,
        entity_id,
        tzinfo=tzinfo,
        lookback_hours=lookback_hours,
        numeric=numeric,
        measurement_candidates=measurement_candidates,
    )

def safe_query_entity_last_value(
    influx,
    entity_id,
    tzinfo=None,
    lookback_hours=72,
    numeric=True,
    label=None,
    measurement_candidates=None,
):
    return INFLUX_SERVICE.safe_query_entity_last_value(
        influx,
        entity_id,
        tzinfo=tzinfo,
        lookback_hours=lookback_hours,
        numeric=numeric,
        label=label,
        measurement_candidates=measurement_candidates,
    )

def query_recent_slot_profile(influx, entity_id, tzinfo, days=7, interval="15m", measurement_candidates=None):
    if not entity_id:
        return {}
    today_start_local = datetime.now(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = today_start_local - timedelta(days=max(1, int(days)))
    points = query_entity_series(
        influx,
        entity_id,
        start_local.astimezone(timezone.utc),
        today_start_local.astimezone(timezone.utc),
        interval=interval,
        tzinfo=tzinfo,
        numeric=True,
        measurement_candidates=measurement_candidates,
    )
    return build_slot_avg_profile(points, tzinfo=tzinfo)

def query_recent_slot_profile_by_day_type(
    influx,
    entity_id,
    tzinfo,
    target_date,
    days=28,
    interval="15m",
    measurement_candidates=None,
):
    if not entity_id:
        return {}
    target_is_weekend = target_date.weekday() >= 5
    today_start_local = datetime.now(tzinfo).replace(hour=0, minute=0, second=0, microsecond=0)
    start_local = today_start_local - timedelta(days=max(1, int(days)))
    points = query_entity_series(
        influx,
        entity_id,
        start_local.astimezone(timezone.utc),
        today_start_local.astimezone(timezone.utc),
        interval=interval,
        tzinfo=tzinfo,
        numeric=True,
        measurement_candidates=measurement_candidates,
    )
    filtered = []
    for point in points:
        time_raw = point.get("time")
        if not time_raw:
            continue
        try:
            dt_local = datetime.fromisoformat(time_raw).astimezone(tzinfo)
        except ValueError:
            continue
        if (dt_local.weekday() >= 5) == target_is_weekend:
            filtered.append(point)
    profile = build_slot_avg_profile(filtered, tzinfo=tzinfo)
    if profile:
        return profile
    return build_slot_avg_profile(points, tzinfo=tzinfo)

def aggregate_power_points(points, interval_minutes, bucket="day", tzinfo=None):
    buckets = {}
    step_kwh_factor = (max(1, interval_minutes) / 60.0) / 1000.0
    tz = tzinfo
    for point in points or []:
        value = point.get("value")
        if value is None:
            continue
        time_raw = point.get("time")
        if not time_raw:
            continue
        try:
            dt_local = datetime.fromisoformat(time_raw)
        except ValueError:
            continue
        if tz:
            if dt_local.tzinfo is None:
                dt_local = dt_local.replace(tzinfo=tz)
            else:
                dt_local = dt_local.astimezone(tz)
        if bucket == "month":
            bucket_key = dt_local.strftime("%Y-%m")
        else:
            bucket_key = dt_local.strftime("%Y-%m-%d")
        buckets[bucket_key] = buckets.get(bucket_key, 0.0) + (float(value) * step_kwh_factor)
    return {k: round(v, 5) for k, v in buckets.items()}

def build_energy_balance_range(period, anchor_value, tzinfo):
    now_local = datetime.now(tzinfo)
    if period == "week":
        try:
            anchor_date = datetime.strptime(anchor_value, "%Y-%m-%d").date() if anchor_value else now_local.date()
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid anchor for week. Use YYYY-MM-DD.") from exc
        start_date = anchor_date - timedelta(days=anchor_date.weekday())
        end_date = start_date + timedelta(days=7)
        start_local = datetime.combine(start_date, datetime_time(0, 0), tzinfo)
        end_local = datetime.combine(end_date, datetime_time(0, 0), tzinfo)
        bucket = "day"
        anchor = start_date.strftime("%Y-%m-%d")
    elif period == "month":
        try:
            if anchor_value:
                year, month = map(int, str(anchor_value).split("-"))
                anchor_date = datetime(year, month, 1).date()
            else:
                anchor_date = now_local.replace(day=1).date()
        except (TypeError, ValueError) as exc:
            raise HTTPException(status_code=400, detail="Invalid anchor for month. Use YYYY-MM.") from exc
        if anchor_date.month == 12:
            end_date = datetime(anchor_date.year + 1, 1, 1).date()
        else:
            end_date = datetime(anchor_date.year, anchor_date.month + 1, 1).date()
        start_local = datetime.combine(anchor_date, datetime_time(0, 0), tzinfo)
        end_local = datetime.combine(end_date, datetime_time(0, 0), tzinfo)
        bucket = "day"
        anchor = anchor_date.strftime("%Y-%m")
    elif period == "year":
        try:
            year = int(anchor_value) if anchor_value else now_local.year
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid anchor for year. Use YYYY.") from exc
        start_local = datetime(year, 1, 1, tzinfo=tzinfo)
        end_local = datetime(year + 1, 1, 1, tzinfo=tzinfo)
        bucket = "month"
        anchor = f"{year:04d}"
    else:
        raise HTTPException(status_code=400, detail="Invalid period. Use week|month|year.")
    return {
        "period": period,
        "anchor": anchor,
        "bucket": bucket,
        "start_local": start_local,
        "end_local": end_local,
        "start_utc": start_local.astimezone(timezone.utc),
        "end_utc": end_local.astimezone(timezone.utc),
    }

def build_energy_balance_buckets(range_info, tzinfo):
    items = []
    start_local = range_info["start_local"]
    end_local = range_info["end_local"]
    bucket = range_info["bucket"]
    current = start_local
    while current < end_local:
        if bucket == "month":
            key = current.strftime("%Y-%m")
            label = current.strftime("%m/%Y")
            if current.month == 12:
                next_dt = current.replace(year=current.year + 1, month=1)
            else:
                next_dt = current.replace(month=current.month + 1)
        else:
            key = current.strftime("%Y-%m-%d")
            label = current.strftime("%d.%m.")
            next_dt = current + timedelta(days=1)
        items.append({"key": key, "label": label, "start": current.isoformat()})
        current = next_dt
    return items

def aggregate_hourly_from_price_entries(entries):
    hours = [None] * 24
    buckets = {hour: [] for hour in range(24)}
    for entry in entries or []:
        time_str = entry.get("time")
        final_price = entry.get("final")
        if time_str is None or final_price is None:
            continue
        try:
            dt_local = datetime.strptime(time_str, "%Y-%m-%d %H:%M")
        except ValueError:
            continue
        buckets[dt_local.hour].append(float(final_price))
    for hour in range(24):
        values = buckets.get(hour) or []
        if values:
            hours[hour] = round(sum(values) / len(values), 5)
    return hours

def aggregate_hourly_from_kwh_points(points):
    hours = [0.0] * 24
    has_any = [False] * 24
    for entry in points or []:
        kwh = entry.get("kwh")
        if kwh is None:
            continue
        time_raw = entry.get("time")
        if not time_raw:
            continue
        try:
            dt_local = datetime.fromisoformat(time_raw)
        except ValueError:
            continue
        hour = dt_local.hour
        hours[hour] += float(kwh)
        has_any[hour] = True
    return [round(hours[idx], 5) if has_any[idx] else None for idx in range(24)]

def build_hybrid_battery_projection(
    now_local,
    soc_percent,
    avg_power_w,
    battery_cfg,
    tzinfo,
    interval_minutes,
    current_energy,
    forecast_payload,
    load_profile,
    pv_profile,
):
    usable_capacity_kwh = battery_cfg["usable_capacity_kwh"]
    reserve_soc = max(0.0, min(100.0, battery_cfg["reserve_soc_percent"]))
    charge_eff = max(0.01, min(1.0, battery_cfg["charge_efficiency"]))
    discharge_eff = max(0.01, min(1.0, battery_cfg["discharge_efficiency"]))
    min_power_threshold_w = battery_cfg["min_power_threshold_w"]

    if soc_percent is None or usable_capacity_kwh <= 0:
        return None

    step_minutes = max(5, min(60, int(interval_minutes or 15)))
    step_hours = step_minutes / 60.0
    current_energy_kwh = usable_capacity_kwh * max(0.0, min(100.0, soc_percent)) / 100.0
    target_full_kwh = usable_capacity_kwh
    target_reserve_kwh = usable_capacity_kwh * reserve_soc / 100.0
    end_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    current_load_w = current_energy.get("house_load_w") if isinstance(current_energy, dict) else None
    current_pv_w = current_energy.get("pv_power_total_w") if isinstance(current_energy, dict) else None
    power_now_w = forecast_payload.get("power_now_w") if isinstance(forecast_payload, dict) else None
    energy_next_hour_kwh = forecast_payload.get("energy_next_hour_kwh") if isinstance(forecast_payload, dict) else None
    remaining_today_kwh = (
        forecast_payload.get("energy_production_today_remaining_kwh") if isinstance(forecast_payload, dict) else None
    )

    if not load_profile and current_load_w is None:
        return None
    if not pv_profile and power_now_w is None and current_pv_w is None:
        return None

    future_steps = []
    probe_time = now_local
    max_points = int((24 * 60) / step_minutes) + 2
    for _ in range(max_points):
        if probe_time > end_of_day_local:
            break
        future_steps.append(probe_time)
        probe_time = probe_time + timedelta(minutes=step_minutes)
    if not future_steps:
        return None

    base_pv_power = []
    for dt_local in future_steps:
        slot = get_slot_index_for_dt(dt_local)
        base_pv_power.append(float(pv_profile.get(slot, current_pv_w or power_now_w or 0.0)))

    # Scale historical PV shape to today's remaining Forecast.Solar energy (if available).
    if remaining_today_kwh is not None and remaining_today_kwh >= 0:
        base_energy_kwh = sum(max(0.0, p) * step_hours / 1000.0 for p in base_pv_power)
        if base_energy_kwh > 0:
            scale = remaining_today_kwh / base_energy_kwh
            scale = max(0.0, min(scale, 5.0))
            base_pv_power = [p * scale for p in base_pv_power]

    # Anchor immediate forecast to current Forecast.Solar now power if available.
    if base_pv_power and power_now_w is not None:
        base_pv_power[0] = float(power_now_w)

    # Use Forecast.Solar next-hour energy as average power for the next hour slots.
    if energy_next_hour_kwh is not None and len(future_steps) > 1:
        next_hour_start = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        next_hour_end = next_hour_start + timedelta(hours=1)
        next_hour_avg_w = max(0.0, float(energy_next_hour_kwh) * 1000.0)
        for idx, dt_local in enumerate(future_steps):
            if next_hour_start <= dt_local < next_hour_end:
                base_pv_power[idx] = next_hour_avg_w

    projection_points = []
    eta_to_full_minutes = None
    eta_to_reserve_minutes = None
    eta_to_full_at = None
    eta_to_reserve_at = None
    state = "idle"
    sim_energy_kwh = current_energy_kwh
    last_pred_battery_w = None

    for idx, dt_local in enumerate(future_steps):
        slot = get_slot_index_for_dt(dt_local)
        predicted_load_w = float(load_profile.get(slot, current_load_w or 0.0))
        predicted_pv_w = max(0.0, float(base_pv_power[idx] if idx < len(base_pv_power) else 0.0))
        predicted_battery_w = predicted_pv_w - predicted_load_w

        # Blend with measured battery trend to reduce jumps at "now".
        if avg_power_w is not None:
            blend_weight = 0.55 if idx == 0 else (0.35 if idx < 4 else 0.15)
            predicted_battery_w = (predicted_battery_w * (1 - blend_weight)) + (avg_power_w * blend_weight)

        last_pred_battery_w = predicted_battery_w
        if predicted_battery_w > min_power_threshold_w:
            state = "charging"
        elif predicted_battery_w < -min_power_threshold_w:
            state = "discharging"
        else:
            state = "idle"

        projection_points.append(
            {
                "time": dt_local.isoformat(),
                "time_utc": to_rfc3339(dt_local.astimezone(timezone.utc)),
                "soc_percent": round(max(0.0, min(100.0, (sim_energy_kwh / usable_capacity_kwh) * 100.0)), 3),
                "predicted_load_w": round(predicted_load_w, 3),
                "predicted_pv_w": round(predicted_pv_w, 3),
                "predicted_battery_w": round(predicted_battery_w, 3),
            }
        )

        if idx == len(future_steps) - 1:
            break

        delta_kwh = (predicted_battery_w / 1000.0) * step_hours
        if delta_kwh >= 0:
            delta_kwh *= charge_eff
        else:
            delta_kwh /= discharge_eff
        next_energy_kwh = min(max(0.0, sim_energy_kwh + delta_kwh), usable_capacity_kwh)

        if eta_to_full_minutes is None and sim_energy_kwh < target_full_kwh <= next_energy_kwh:
            eta_to_full_minutes = round((dt_local + timedelta(minutes=step_minutes) - now_local).total_seconds() / 60)
            eta_to_full_at = (now_local + timedelta(minutes=eta_to_full_minutes)).isoformat()
        if eta_to_reserve_minutes is None and sim_energy_kwh > target_reserve_kwh >= next_energy_kwh:
            eta_to_reserve_minutes = round((dt_local + timedelta(minutes=step_minutes) - now_local).total_seconds() / 60)
            eta_to_reserve_at = (now_local + timedelta(minutes=eta_to_reserve_minutes)).isoformat()

        sim_energy_kwh = next_energy_kwh

    confidence = "medium" if (remaining_today_kwh is not None and load_profile and pv_profile) else "low"
    if last_pred_battery_w is not None:
        if abs(last_pred_battery_w) < min_power_threshold_w:
            state = "idle"
        elif last_pred_battery_w > 0:
            state = "charging"
        else:
            state = "discharging"

    return {
        "method": "hybrid_forecast_load_profile",
        "confidence": confidence,
        "state": state,
        "eta_to_full_minutes": eta_to_full_minutes,
        "eta_to_reserve_minutes": eta_to_reserve_minutes,
        "eta_to_full_at": eta_to_full_at,
        "eta_to_reserve_at": eta_to_reserve_at,
        "step_minutes": step_minutes,
        "points": projection_points,
        "inputs": {
            "uses_load_profile": bool(load_profile),
            "uses_pv_profile": bool(pv_profile),
            "uses_forecast_remaining": remaining_today_kwh is not None,
            "uses_forecast_power_now": power_now_w is not None,
            "uses_forecast_next_hour": energy_next_hour_kwh is not None,
        },
    }

def build_battery_history_points(soc_points, power_points):
    by_time = {}
    for point in soc_points or []:
        key = point["time"]
        row = by_time.setdefault(key, {"time": point["time"], "time_utc": point["time_utc"]})
        row["soc_percent"] = point.get("value")
    for point in power_points or []:
        key = point["time"]
        row = by_time.setdefault(key, {"time": point["time"], "time_utc": point["time_utc"]})
        row["battery_power_w"] = point.get("value")
    rows = list(by_time.values())
    rows.sort(key=lambda item: item.get("time_utc") or item.get("time") or "")
    return rows

def get_last_non_null_value(points):
    for point in reversed(points or []):
        value = point.get("value")
        if value is not None:
            return point
    return None

def iso_to_display_hhmm(iso_value):
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
    except ValueError:
        return str(iso_value)
    return dt.strftime("%H:%M")

def build_battery_projection(now_local, soc_percent, avg_power_w, battery_cfg, tzinfo):
    usable_capacity_kwh = battery_cfg["usable_capacity_kwh"]
    reserve_soc = max(0.0, min(100.0, battery_cfg["reserve_soc_percent"]))
    min_power_threshold_w = battery_cfg["min_power_threshold_w"]
    charge_eff = max(0.01, min(1.0, battery_cfg["charge_efficiency"]))
    discharge_eff = max(0.01, min(1.0, battery_cfg["discharge_efficiency"]))

    if soc_percent is None or usable_capacity_kwh <= 0 or avg_power_w is None:
        return {
            "method": "trend",
            "confidence": "low",
            "state": "unknown",
            "eta_to_full_minutes": None,
            "eta_to_reserve_minutes": None,
            "eta_to_full_at": None,
            "eta_to_reserve_at": None,
            "points": [],
        }

    if abs(avg_power_w) < min_power_threshold_w:
        return {
            "method": "trend",
            "confidence": "low",
            "state": "idle",
            "eta_to_full_minutes": None,
            "eta_to_reserve_minutes": None,
            "eta_to_full_at": None,
            "eta_to_reserve_at": None,
            "points": [],
        }

    current_energy_kwh = usable_capacity_kwh * max(0.0, min(100.0, soc_percent)) / 100.0
    target_full_kwh = usable_capacity_kwh
    target_reserve_kwh = usable_capacity_kwh * reserve_soc / 100.0

    if avg_power_w > 0:
        delta_kwh_per_hour = (avg_power_w / 1000.0) * charge_eff
        state = "charging"
    else:
        delta_kwh_per_hour = (avg_power_w / 1000.0) / discharge_eff
        state = "discharging"

    eta_to_full_minutes = None
    eta_to_reserve_minutes = None
    eta_to_full_at = None
    eta_to_reserve_at = None

    if delta_kwh_per_hour > 0 and current_energy_kwh < target_full_kwh:
        eta_hours = (target_full_kwh - current_energy_kwh) / delta_kwh_per_hour if delta_kwh_per_hour else None
        if eta_hours is not None and eta_hours >= 0:
            eta_to_full_minutes = round(eta_hours * 60)
            eta_to_full_at = (now_local + timedelta(minutes=eta_to_full_minutes)).isoformat()
    if delta_kwh_per_hour < 0 and current_energy_kwh > target_reserve_kwh:
        eta_hours = (current_energy_kwh - target_reserve_kwh) / abs(delta_kwh_per_hour) if delta_kwh_per_hour else None
        if eta_hours is not None and eta_hours >= 0:
            eta_to_reserve_minutes = round(eta_hours * 60)
            eta_to_reserve_at = (now_local + timedelta(minutes=eta_to_reserve_minutes)).isoformat()

    end_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    step_minutes = max(5, min(60, parse_influx_interval_to_minutes("15m")))
    projection_points = []
    proj_time = now_local
    proj_energy = current_energy_kwh
    step_delta = delta_kwh_per_hour * (step_minutes / 60.0)
    max_points = 96

    for _ in range(max_points):
        if proj_time > end_of_day_local:
            break
        projection_points.append(
            {
                "time": proj_time.isoformat(),
                "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                "soc_percent": round(max(0.0, min(100.0, (proj_energy / usable_capacity_kwh) * 100.0)), 3),
            }
        )
        next_time = proj_time + timedelta(minutes=step_minutes)
        if next_time > end_of_day_local:
            break
        proj_energy = min(max(0.0, proj_energy + step_delta), usable_capacity_kwh)
        proj_time = next_time
        if state == "charging" and proj_energy >= target_full_kwh:
            projection_points.append(
                {
                    "time": proj_time.isoformat(),
                    "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                    "soc_percent": 100.0,
                }
            )
            break
        if state == "discharging" and proj_energy <= target_reserve_kwh:
            projection_points.append(
                {
                    "time": proj_time.isoformat(),
                    "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                    "soc_percent": round((target_reserve_kwh / usable_capacity_kwh) * 100.0, 3),
                }
            )
            break

    return {
        "method": "trend",
        "confidence": "low",
        "state": state,
        "eta_to_full_minutes": eta_to_full_minutes,
        "eta_to_reserve_minutes": eta_to_reserve_minutes,
        "eta_to_full_at": eta_to_full_at,
        "eta_to_reserve_at": eta_to_reserve_at,
        "step_minutes": step_minutes,
        "points": projection_points,
    }

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
    except (OSError, json.JSONDecodeError, TypeError):
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
    except (OSError, json.JSONDecodeError, TypeError):
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
            "fetched_at": utc_now_iso_z(),
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
    except (OSError, json.JSONDecodeError, TypeError):
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
        "meta": {"key": cache_key, "fetched_at": utc_now_iso_z()},
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
    except (OSError, json.JSONDecodeError, TypeError):
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
        "meta": {"key": cache_key, "fetched_at": utc_now_iso_z()},
        "data": data,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    logger.info("Saved export cache for %s to %s", date_str, path)

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
        try:
            hour = int(entry.get("hour", 0))
            minute = int(entry.get("minute", 0))
            price_czk_mwh = float(entry.get("priceCZK"))
        except (TypeError, ValueError):
            logger.warning("Skipping invalid API price row for %s: %s", date_str, entry)
            continue
        spot_kwh = price_czk_mwh / 1000.0
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

def build_entries_from_ote(
    cfg: dict[str, Any],
    date_str: str,
    items: list[dict[str, Any]],
    fee_snapshot: dict[str, Any],
    eur_to_czk_rate: float,
) -> list[dict[str, Any]]:
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

def build_entries_from_spot_html(
    cfg: dict[str, Any],
    date_str: str,
    fee_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
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

def build_ote_query(start_date: str, end_date: str) -> str:
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

def fetch_ote_prices_xml(start_date: datetime_date, end_date: datetime_date) -> str:
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

def parse_ote_prices_xml(xml_text: str) -> dict[str, list[dict[str, Any]]]:
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

def extract_eur_czk_from_cnb_payload(payload: Any) -> float | None:
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

def get_eur_czk_rate_for_date(day: datetime_date) -> float:
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

def get_ote_entries_for_dates(
    cfg: dict[str, Any],
    dates: list[str],
    tzinfo,
) -> dict[str, list[dict[str, Any]]]:
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

def apply_fee_snapshot(
    entries: list[dict[str, Any]],
    cfg: dict[str, Any],
    fee_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    if not entries:
        return []
    adjusted = []
    for entry in entries:
        hour = entry.get("hour", 0)
        spot = entry.get("spot", 0)
        final = calculate_final_price(spot, hour, cfg, fee_snapshot)
        adjusted.append({**entry, "final": final})
    return adjusted

def get_prices_for_date(
    cfg: dict[str, Any],
    date_str: str,
    tzinfo,
    force_refresh: bool = False,
    include_neighbor_live: bool = False,
) -> list[dict[str, Any]]:
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
                except (HTTPException, RequestException, ValueError, TypeError, KeyError) as exc:
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
            except (RequestException, ValueError, TypeError, KeyError) as exc:
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
                except (HTTPException, RequestException, ValueError, TypeError, KeyError) as exc:
                    mark_ote_unavailable(exc)
                    logger.warning("OTE historical prices fetch failed for %s: %s", date_str, exc)
        elif provider == PRICE_PROVIDER_SPOT and not entries:
            try:
                entries = build_entries_from_spot_html(cfg, date_str, fee_snapshot)
                effective_provider = PRICE_PROVIDER_SPOT
            except (RequestException, ValueError, TypeError, KeyError) as exc:
                logger.warning("Spot historical prices fetch failed for %s: %s", date_str, exc)
                entries = []

    if entries:
        PRICES_CACHE[date_str] = entries
        PRICES_CACHE_PROVIDER[date_str] = effective_provider
        save_prices_cache(date_str, entries, provider=effective_provider)
    return apply_fee_snapshot(entries, cfg, fee_snapshot)

def build_price_map_for_date(
    cfg: dict[str, Any],
    date_str: str,
    tzinfo,
) -> tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]:
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
        if cached and should_use_daily_cache(date, cache_path, cache_meta, tzinfo, CONSUMPTION_CACHE_TTL_SECONDS):
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
    except (HTTPException, RequestException) as exc:
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
        if cached and should_use_daily_cache(date, cache_path, cache_meta, tzinfo, EXPORT_CACHE_TTL_SECONDS):
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
    except (HTTPException, RequestException) as exc:
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


PRICES_SERVICE = PricesService(
    get_prices_for_date=get_prices_for_date,
    get_price_provider=get_price_provider,
    clear_prices_cache_for_date=clear_prices_cache_for_date,
)
COSTS_SERVICE = CostsService(
    get_consumption_points=get_consumption_points,
    build_price_map_for_date=build_price_map_for_date,
)
EXPORT_SERVICE = ExportService(
    get_export_points=get_export_points,
    build_price_map_for_date=build_price_map_for_date,
    get_fee_snapshot_for_date=get_fee_snapshot_for_date,
    get_sell_coefficient_kwh=get_sell_coefficient_kwh,
)
BILLING_SERVICE = BillingService(
    get_consumption_points=get_consumption_points,
    get_export_points=get_export_points,
    build_price_map_for_date=build_price_map_for_date,
    get_export_entity_id=get_export_entity_id,
    get_fee_snapshot_for_date=get_fee_snapshot_for_date,
    get_sell_coefficient_kwh=get_sell_coefficient_kwh,
    compute_fixed_breakdown_for_day=compute_fixed_breakdown_for_day,
)
BATTERY_SERVICE = BatteryService(
    get_influx_cfg=get_influx_cfg,
    get_local_tz=get_local_tz,
    get_battery_cfg=get_battery_cfg,
    get_energy_entities_cfg=get_energy_entities_cfg,
    get_forecast_solar_cfg=get_forecast_solar_cfg,
    parse_time_range=parse_time_range,
    has_battery_required_cfg=has_battery_required_cfg,
    query_entity_series=query_entity_series,
    build_battery_history_points=build_battery_history_points,
    get_last_non_null_value=get_last_non_null_value,
    average_recent_power=average_recent_power,
    safe_query_entity_last_value=safe_query_entity_last_value,
    parse_influx_interval_to_minutes=parse_influx_interval_to_minutes,
    query_recent_slot_profile_by_day_type=query_recent_slot_profile_by_day_type,
    build_hybrid_battery_projection=build_hybrid_battery_projection,
    build_battery_projection=build_battery_projection,
    iso_to_display_hhmm=iso_to_display_hhmm,
    logger=logger,
)
INSIGHTS_SERVICE = InsightsService(
    get_influx_cfg=get_influx_cfg,
    get_energy_entities_cfg=get_energy_entities_cfg,
    build_energy_balance_range=build_energy_balance_range,
    parse_influx_interval_to_minutes=parse_influx_interval_to_minutes,
    query_entity_series=query_entity_series,
    aggregate_power_points=aggregate_power_points,
    build_energy_balance_buckets=build_energy_balance_buckets,
    get_prices_for_date=get_prices_for_date,
    aggregate_hourly_from_price_entries=aggregate_hourly_from_price_entries,
    get_consumption_points=get_consumption_points,
    get_export_points=get_export_points,
    aggregate_hourly_from_kwh_points=aggregate_hourly_from_kwh_points,
    logger=logger,
)
SCHEDULE_SERVICE = ScheduleService(get_prices_for_date=get_prices_for_date)


def get_config():
    return load_config()

def save_config(new_config: dict = Body(...)):
    if isinstance(new_config, dict):
        new_config["price_provider"] = normalize_price_provider(new_config.get("price_provider"))
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_config, f, allow_unicode=True)
    if STORAGE_DIR:
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(OPTIONS_BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(new_config, f)
    return {"status": "ok", "message": "Konfigurace ulozena"}


def get_fees_history(cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    history = ensure_fee_history(cfg, tzinfo)
    history.sort(key=lambda x: x.get("effective_from", ""))
    return {"history": history}


def update_fees_history(payload: dict = Body(...), cfg=None, tzinfo=None):
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Invalid payload.")
    history = payload.get("history")
    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="Invalid history payload.")

    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
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

def get_cache_status():
    return cache_status()

def get_version():
    return {"version": APP_VERSION}


# --- Spotove ceny ---
def get_spot_prices():
    # Endpoint vraci ctvrt-hodinova data.
    url = "https://spotovaelektrina.cz/api/v1/price/get-prices-json-qh"
    logger.info("Fetching prices from API: %s", url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def get_prices(date: str = Query(default=None), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return PRICES_SERVICE.get_prices(date=date, cfg=cfg, tzinfo=tzinfo)

def refresh_prices(payload: dict = Body(default=None), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return PRICES_SERVICE.refresh_prices(payload=payload, cfg=cfg, tzinfo=tzinfo)

def get_consumption(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
    cfg=None,
):
    cfg, _ = resolve_config_and_timezone(cfg=cfg)
    result = get_consumption_points(cfg, date, start, end)
    return {
        "range": result["range"],
        "interval": result["interval"],
        "entity_id": result["entity_id"],
        "points": result["points"],
        "from_cache": result.get("from_cache", False),
        "cache_fallback": result.get("cache_fallback", False),
    }

def get_costs(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
    cfg=None,
    tzinfo=None,
):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return COSTS_SERVICE.get_costs(
        date=date,
        start=start,
        end=end,
        cfg=cfg,
        tzinfo=tzinfo,
    )

def get_export(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
    cfg=None,
    tzinfo=None,
):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return EXPORT_SERVICE.get_export(
        date=date,
        start=start,
        end=end,
        cfg=cfg,
        tzinfo=tzinfo,
    )

def get_battery(date: str = Query(default=None), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return BATTERY_SERVICE.get_battery(date=date, cfg=cfg, tzinfo=tzinfo)

def get_energy_balance(
    period: str = Query(default="week"),
    anchor: str = Query(default=None),
    cfg=None,
    tzinfo=None,
):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return INSIGHTS_SERVICE.get_energy_balance(period=period, anchor=anchor, cfg=cfg, tzinfo=tzinfo)

def get_history_heatmap(
    month: str = Query(...),
    metric: str = Query(default="buy"),
    cfg=None,
    tzinfo=None,
):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return INSIGHTS_SERVICE.get_history_heatmap(month=month, metric=metric, cfg=cfg, tzinfo=tzinfo)


def get_schedule(
    duration: int = Query(default=120, ge=1, le=360),
    count: int = Query(default=3, ge=1, le=3),
    cfg=None,
    tzinfo=None,
):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return SCHEDULE_SERVICE.get_schedule(duration=duration, count=count, cfg=cfg, tzinfo=tzinfo)

def get_daily_summary(month: str = Query(...), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return BILLING_SERVICE.get_daily_summary(month=month, cfg=cfg, tzinfo=tzinfo)

def get_billing_month(month: str = Query(...), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return BILLING_SERVICE.get_billing_month(month=month, cfg=cfg, tzinfo=tzinfo)

def get_billing_year(year: int = Query(..., ge=2000, le=2100), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    return BILLING_SERVICE.get_billing_year(year=year, cfg=cfg, tzinfo=tzinfo)


def get_prefetch_lock_path():
    if STORAGE_DIR:
        return STORAGE_DIR / "prefetch-scheduler.lock"
    return Path("/tmp") / "elektroapp-prefetch-scheduler.lock"


def _clear_stale_prefetch_lock(lock_path):
    if not lock_path.exists():
        return
    try:
        age_seconds = max(0.0, time_module.time() - lock_path.stat().st_mtime)
        if age_seconds > PREFETCH_LOCK_STALE_SECONDS:
            lock_path.unlink(missing_ok=True)
            logger.warning("Removed stale prefetch scheduler lock: %s", lock_path)
    except OSError as exc:
        logger.warning("Unable to evaluate stale prefetch lock %s: %s", lock_path, exc)


def acquire_prefetch_process_lock():
    lock_path = get_prefetch_lock_path()
    try:
        lock_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logger.warning("Cannot create prefetch lock directory (%s): %s", lock_path.parent, exc)
        return False

    _clear_stale_prefetch_lock(lock_path)

    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        logger.info("Prefetch scheduler lock already held by another process: %s", lock_path)
        return False
    except OSError as exc:
        logger.warning("Cannot create prefetch scheduler lock %s: %s", lock_path, exc)
        return False

    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "pid": os.getpid(),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
            )
        )

    RUNTIME_STATE.prefetch_lock_owned = True
    RUNTIME_STATE.prefetch_lock_path = lock_path
    return True


def release_prefetch_process_lock():
    if not RUNTIME_STATE.prefetch_lock_owned or not RUNTIME_STATE.prefetch_lock_path:
        return
    try:
        RUNTIME_STATE.prefetch_lock_path.unlink(missing_ok=True)
    except OSError as exc:
        logger.warning("Unable to remove prefetch scheduler lock %s: %s", RUNTIME_STATE.prefetch_lock_path, exc)
    finally:
        RUNTIME_STATE.prefetch_lock_owned = False
        RUNTIME_STATE.prefetch_lock_path = None


def start_prefetch_scheduler():
    with RUNTIME_STATE.prefetch_thread_guard:
        if RUNTIME_STATE.prefetch_thread and RUNTIME_STATE.prefetch_thread.is_alive():
            logger.info("Prefetch scheduler already running in current process.")
            return False

        if not acquire_prefetch_process_lock():
            return False

        RUNTIME_STATE.prefetch_thread = threading.Thread(
            target=schedule_prefetch_loop,
            daemon=True,
            name="prefetch-scheduler",
        )
        RUNTIME_STATE.prefetch_thread.start()
        logger.info("Prefetch scheduler started in process %s", os.getpid())
        return True


def schedule_prefetch_loop():
    while True:
        try:
            cfg = load_config()
            provider = get_price_provider(cfg)
            _, tzinfo = resolve_config_and_timezone(cfg=cfg)
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
                    except (HTTPException, RequestException, ValueError, TypeError) as exc:
                        logger.warning("Prefetch failed for %s: %s", tomorrow_str, exc)
                    if has_price_cache(tomorrow_str, provider=provider):
                        next_run = datetime.combine(now.date() + timedelta(days=1), datetime_time(13, 5), tzinfo)
                    else:
                        next_run = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)

            sleep_seconds = max(30, (next_run - datetime.now(tzinfo)).total_seconds())
        except (HTTPException, RequestException, OSError, ValueError, TypeError) as exc:
            logger.warning("Scheduler iteration failed, retrying in 5 minutes: %s", exc)
            sleep_seconds = 300
        time_module.sleep(sleep_seconds)


atexit.register(release_prefetch_process_lock)


# --- Startup logging ---
def log_cache_status():
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
