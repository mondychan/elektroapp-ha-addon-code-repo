import os
import json
import yaml
import logging
from pathlib import Path
from datetime import datetime
from typing import Any
from api import get_local_tz
from pricing import (
    build_fee_snapshot,
    normalize_dph_percent,
    normalize_price_provider,
    parse_vt_periods,
    _safe_float,
)

logger = logging.getLogger("uvicorn.error")

CONFIG_FILE = "config.yaml"
HA_OPTIONS_FILE = Path("/data/options.json")
CONFIG_DIR = Path("/config")
_storage_env = os.getenv("ELEKTROAPP_STORAGE")
if _storage_env:
    STORAGE_DIR = Path(_storage_env)
else:
    STORAGE_DIR = CONFIG_DIR / "elektroapp" if CONFIG_DIR.exists() else Path("/data")

OPTIONS_BACKUP_FILE = STORAGE_DIR / "options.json"
FEES_HISTORY_FILE = STORAGE_DIR / "fees-history.json"

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

def update_fees_history_logic(history_payload: list, tzinfo):
    today = datetime.now(tzinfo).date()

    normalized_entries = []
    seen_dates = set()
    for entry in history_payload:
        if not isinstance(entry, dict):
            continue
        date_str = entry.get("effective_from")
        if not date_str:
            continue
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Invalid effective_from: {date_str}")
        
        if date_str in seen_dates:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=f"Duplicated effective_from: {date_str}")
        seen_dates.add(date_str)
        
        if date_obj > today:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="effective_from cannot be in the future.")
            
        effective_to = entry.get("effective_to")
        effective_to_date = None
        if effective_to:
            try:
                effective_to_date = datetime.strptime(effective_to, "%Y-%m-%d").date()
            except ValueError:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=f"Invalid effective_to: {effective_to}")
            if effective_to_date > today:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="effective_to cannot be in the future.")
            if effective_to_date < date_obj:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="effective_to must be >= effective_from.")
        
        from pricing import normalize_fee_snapshot
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
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="History cannot be empty.")

    normalized_entries.sort(key=lambda x: x["from_date"])
    from datetime import timedelta
    for idx, entry in enumerate(normalized_entries[:-1]):
        next_entry = normalized_entries[idx + 1]
        if entry["to_date"] is None:
            computed_to = next_entry["from_date"] - timedelta(days=1)
            if computed_to < entry["from_date"]:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="effective_to must be >= effective_from.")
            entry["to_date"] = computed_to
            entry["effective_to"] = computed_to.strftime("%Y-%m-%d")
        if entry["to_date"] >= next_entry["from_date"]:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Fee history ranges overlap.")

    normalized = []
    for entry in normalized_entries:
        record = {"effective_from": entry["effective_from"], "snapshot": entry["snapshot"]}
        if entry["effective_to"]:
            record["effective_to"] = entry["effective_to"]
        normalized.append(record)
    
    save_fee_history(normalized)
    return normalized

def resolve_config_and_timezone(cfg=None, tzinfo=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    if not tzinfo:
        tzinfo = get_local_tz(cfg.get("influxdb", {}).get("timezone"))
    return cfg, tzinfo

def get_influx_cfg(cfg):
    influx = cfg.get("influxdb", {})
    required = ["host", "port", "database", "measurement", "field", "entity_id"]
    missing = [key for key in required if not influx.get(key)]
    if missing:
        from fastapi import HTTPException
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

