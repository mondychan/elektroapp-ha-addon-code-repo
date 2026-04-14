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


def _read_json_file(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError, TypeError):
        return None


def _write_json_file(path: Path, payload: dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        return True
    except OSError as exc:
        logger.warning("Failed to write config mirror %s: %s", path, exc)
        return False


def _count_config_customizations(defaults: Any, candidate: Any) -> int:
    if isinstance(defaults, dict) and isinstance(candidate, dict):
        keys = set(defaults.keys()) | set(candidate.keys())
        return sum(_count_config_customizations(defaults.get(key), candidate.get(key)) for key in keys)
    if isinstance(defaults, list) and isinstance(candidate, list):
        if defaults == candidate:
            return 0
        if not defaults and candidate:
            return len(candidate)
        return 1
    if defaults == candidate:
        return 0
    return 1


def save_options_sync(options: dict[str, Any]) -> dict[str, bool]:
    results: dict[str, bool] = {}
    for path in (HA_OPTIONS_FILE, OPTIONS_BACKUP_FILE):
        if not path:
            continue
        results[str(path)] = _write_json_file(path, options)
    return results

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
    default_cfg = cfg if isinstance(cfg, dict) else {}

    option_sources: list[tuple[float, int, Path, dict[str, Any]]] = []
    for options_path in (HA_OPTIONS_FILE, OPTIONS_BACKUP_FILE):
        options = _read_json_file(options_path)
        if options is None:
            continue
        try:
            mtime = options_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        customization_score = _count_config_customizations(default_cfg, options)
        option_sources.append((mtime, customization_score, options_path, options))

    if option_sources:
        custom_sources = [item for item in option_sources if item[1] > 0]
        candidate_sources = custom_sources or option_sources
        candidate_sources.sort(key=lambda item: item[0], reverse=True)
        _, _, selected_path, selected_options = candidate_sources[0]
        cfg = merge_config(cfg, selected_options)

        for mirror_path in (HA_OPTIONS_FILE, OPTIONS_BACKUP_FILE):
            if mirror_path == selected_path:
                continue
            _write_json_file(mirror_path, selected_options)

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
        "power_next_hour_entity_id": forecast.get("power_next_hour_entity_id"),
        "power_next_12hours_entity_id": forecast.get("power_next_12hours_entity_id"),
        "power_next_24hours_entity_id": forecast.get("power_next_24hours_entity_id"),
        "energy_current_hour_entity_id": forecast.get("energy_current_hour_entity_id"),
        "energy_next_hour_entity_id": forecast.get("energy_next_hour_entity_id"),
        "energy_production_today_entity_id": forecast.get("energy_production_today_entity_id"),
        "energy_production_today_remaining_entity_id": forecast.get("energy_production_today_remaining_entity_id"),
        "energy_production_tomorrow_entity_id": forecast.get("energy_production_tomorrow_entity_id"),
        "power_highest_peak_time_today_entity_id": forecast.get("power_highest_peak_time_today_entity_id"),
        "power_highest_peak_time_tomorrow_entity_id": forecast.get("power_highest_peak_time_tomorrow_entity_id"),
    }

def get_alerts_cfg(cfg):
    alerts = cfg.get("alerts", {}) if isinstance(cfg.get("alerts"), dict) else {}
    return {
        "low_price_threshold": _safe_float(alerts.get("low_price_threshold", 1.5)),
        "high_price_threshold": _safe_float(alerts.get("high_price_threshold", 5.0)),
    }

def get_pnd_cfg(cfg):
    pnd = cfg.get("pnd", {}) if isinstance(cfg.get("pnd"), dict) else {}
    username = pnd.get("username")
    password = pnd.get("password")
    meter_id = pnd.get("meter_id")
    start_hour = int(_safe_float(pnd.get("nightly_sync_window_start_hour", 2)) or 2)
    end_hour = int(_safe_float(pnd.get("nightly_sync_window_end_hour", 7)) or 7)
    start_hour = max(0, min(23, start_hour))
    end_hour = max(start_hour, min(23, end_hour))
    return {
        "enabled": bool(pnd.get("enabled", False)),
        "username": str(username).strip() if username else "",
        "password": str(password) if password else "",
        "meter_id": str(meter_id).strip() if meter_id else "",
        "verify_on_startup": bool(pnd.get("verify_on_startup", True)),
        "nightly_sync_enabled": bool(pnd.get("nightly_sync_enabled", True)),
        "nightly_sync_window_start_hour": start_hour,
        "nightly_sync_window_end_hour": end_hour,
    }


def get_hp_cfg(cfg):
    hp = cfg.get("hp", {}) if isinstance(cfg.get("hp"), dict) else {}
    raw_entities = hp.get("entities") if isinstance(hp.get("entities"), list) else []
    raw_overrides = hp.get("overrides") if isinstance(hp.get("overrides"), list) else []
    normalized_entities = []
    normalized_overrides = []

    source_mode = str(hp.get("source_mode") or "manual").strip().lower()
    if source_mode not in {"manual", "prefix", "regex"}:
        source_mode = "manual"

    scan = hp.get("scan", {}) if isinstance(hp.get("scan"), dict) else {}
    normalized_scan = {
        "prefix": str(scan.get("prefix") or "").strip(),
        "regex": str(scan.get("regex") or "").strip(),
        "allowlist": [str(item).strip() for item in scan.get("allowlist", []) if str(item).strip()] if isinstance(scan.get("allowlist"), list) else [],
        "blocklist": [str(item).strip() for item in scan.get("blocklist", []) if str(item).strip()] if isinstance(scan.get("blocklist"), list) else [],
        "include_domains": [str(item).strip() for item in scan.get("include_domains", []) if str(item).strip()] if isinstance(scan.get("include_domains"), list) else ["sensor", "binary_sensor"],
        "exclude_unavailable": bool(scan.get("exclude_unavailable", True)),
    }
    if not normalized_scan["include_domains"]:
        normalized_scan["include_domains"] = ["sensor", "binary_sensor"]

    defaults = hp.get("defaults", {}) if isinstance(hp.get("defaults"), dict) else {}
    kpi_mode_numeric = str(defaults.get("kpi_mode_numeric") or "last").strip().lower()
    if kpi_mode_numeric not in {"last", "min", "max", "avg", "sum", "delta"}:
        kpi_mode_numeric = "last"
    normalized_defaults = {
        "kpi_enabled": bool(defaults.get("kpi_enabled", True)),
        "chart_enabled_numeric": bool(defaults.get("chart_enabled_numeric", True)),
        "chart_enabled_state": bool(defaults.get("chart_enabled_state", False)),
        "kpi_mode_numeric": kpi_mode_numeric,
        "kpi_mode_state": "last",
        "decimals": None,
    }
    defaults_decimals = defaults.get("decimals")
    if defaults_decimals not in (None, ""):
        normalized_defaults["decimals"] = max(0, min(6, int(_safe_float(defaults_decimals) or 0)))

    for item in raw_entities:
        if not isinstance(item, dict):
            continue
        display_kind = str(item.get("display_kind") or "numeric").strip().lower()
        source_kind = str(item.get("source_kind") or "instant").strip().lower()
        kpi_mode = str(item.get("kpi_mode") or "last").strip().lower()

        if display_kind == "state" or source_kind == "state":
            display_kind = "state"
            source_kind = "state"
            kpi_mode = "last"

        decimals_value = item.get("decimals")
        if decimals_value is None or decimals_value == "":
            decimals = None
        else:
            decimals = max(0, min(6, int(_safe_float(decimals_value) or 0)))

        normalized_entities.append(
            {
                "entity_id": str(item.get("entity_id") or "").strip(),
                "label": str(item.get("label") or "").strip(),
                "display_kind": display_kind,
                "source_kind": source_kind,
                "kpi_enabled": bool(item.get("kpi_enabled", True)),
                "chart_enabled": bool(item.get("chart_enabled", False)) if display_kind == "numeric" else False,
                "kpi_mode": kpi_mode,
                "unit": str(item.get("unit")).strip() if item.get("unit") else None,
                "measurement": str(item.get("measurement")).strip() if item.get("measurement") else None,
                "decimals": decimals,
                "device_class": str(item.get("device_class")).strip() if item.get("device_class") else None,
                "state_class": str(item.get("state_class")).strip() if item.get("state_class") else None,
            }
        )

    for item in raw_overrides:
        if not isinstance(item, dict):
            continue
        entity_id = str(item.get("entity_id") or "").strip()
        if not entity_id:
            continue
        display_kind = item.get("display_kind")
        if display_kind is not None:
            display_kind = str(display_kind).strip().lower()
            if display_kind not in {"numeric", "state"}:
                display_kind = None

        source_kind = item.get("source_kind")
        if source_kind is not None:
            source_kind = str(source_kind).strip().lower()
            if source_kind not in {"instant", "counter", "state"}:
                source_kind = None

        kpi_mode = item.get("kpi_mode")
        if kpi_mode is not None:
            kpi_mode = str(kpi_mode).strip().lower()
            if kpi_mode not in {"last", "min", "max", "avg", "sum", "delta"}:
                kpi_mode = None

        decimals_value = item.get("decimals")
        if decimals_value is None or decimals_value == "":
            decimals = None
        else:
            decimals = max(0, min(6, int(_safe_float(decimals_value) or 0)))

        normalized_overrides.append(
            {
                "entity_id": entity_id,
                "enabled": bool(item.get("enabled", True)),
                "label": str(item.get("label")).strip() if item.get("label") else None,
                "display_kind": display_kind,
                "source_kind": source_kind,
                "kpi_enabled": bool(item["kpi_enabled"]) if "kpi_enabled" in item and item.get("kpi_enabled") is not None else None,
                "chart_enabled": bool(item["chart_enabled"]) if "chart_enabled" in item and item.get("chart_enabled") is not None else None,
                "kpi_mode": kpi_mode,
                "unit": str(item.get("unit")).strip() if item.get("unit") else None,
                "measurement": str(item.get("measurement")).strip() if item.get("measurement") else None,
                "decimals": decimals,
            }
        )

    return {
        "enabled": bool(hp.get("enabled", False)),
        "source_mode": source_mode,
        "scan": normalized_scan,
        "defaults": normalized_defaults,
        "entities": normalized_entities,
        "overrides": normalized_overrides,
    }


def has_pnd_required_cfg(pnd_cfg):
    return bool(
        pnd_cfg.get("enabled")
        and pnd_cfg.get("username")
        and pnd_cfg.get("password")
        and pnd_cfg.get("meter_id")
    )

def has_battery_required_cfg(battery_cfg):
    return bool(
        battery_cfg.get("soc_entity_id")
        and battery_cfg.get("power_entity_id")
        and battery_cfg.get("usable_capacity_kwh", 0) > 0
    )
