import os
import json
import yaml
import logging
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timedelta, timezone
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
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        logger.error("Unable to read fee history %s: %s", FEES_HISTORY_FILE, exc)
        return []

def _validate_fee_history(history, *, require_snapshot_schema=True):
    if not isinstance(history, list) or not history:
        raise ValueError("Fee history must be a non-empty list.")
    parsed = []
    for record in history:
        if not isinstance(record, dict) or not isinstance(record.get("snapshot"), dict):
            raise ValueError("Each fee history record must contain a snapshot object.")
        snapshot = record["snapshot"]
        if require_snapshot_schema and not {"dph_percent", "kwh_fees", "fixed"}.issubset(snapshot):
            raise ValueError("Fee history snapshot is missing required pricing fields.")
        if require_snapshot_schema and (not isinstance(snapshot.get("kwh_fees"), dict) or not isinstance(snapshot.get("fixed"), dict)):
            raise ValueError("Fee history pricing fields must be objects.")
        if "prodej" in snapshot and not isinstance(snapshot["prodej"], dict):
            raise ValueError("Fee history prodej must be an object.")
        if "nakup" in snapshot and not isinstance(snapshot["nakup"], dict):
            raise ValueError("Fee history nakup must be an object.")
        start_raw = record.get("effective_from")
        try:
            start = datetime.strptime(start_raw, "%Y-%m-%d").date()
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid effective_from in fee history.") from exc
        end_raw = record.get("effective_to")
        try:
            end = datetime.strptime(end_raw, "%Y-%m-%d").date() if end_raw else None
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid effective_to in fee history.") from exc
        if end and end < start:
            raise ValueError("Fee history effective_to precedes effective_from.")
        parsed.append((start, end))
    if parsed != sorted(parsed, key=lambda value: value[0]):
        raise ValueError("Fee history periods are not ordered.")
    for idx, (start, end) in enumerate(parsed[:-1]):
        next_start = parsed[idx + 1][0]
        if end is None or end >= next_start:
            raise ValueError("Fee history periods overlap or have an open-ended non-final period.")


def _history_backup_path():
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return FEES_HISTORY_FILE.with_name(f"{FEES_HISTORY_FILE.name}.{stamp}.bak")


def _atomic_write_fee_history(history, *, create_backup=True):
    _validate_fee_history(history, require_snapshot_schema=False)
    FEES_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    backup_path = None
    if create_backup and FEES_HISTORY_FILE.exists():
        backup_path = _history_backup_path()
        shutil.copy2(FEES_HISTORY_FILE, backup_path)
    fd, temp_name = tempfile.mkstemp(prefix=f".{FEES_HISTORY_FILE.name}.", suffix=".tmp", dir=FEES_HISTORY_FILE.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_name, FEES_HISTORY_FILE)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise
    return backup_path


def save_fee_history(history):
    return _atomic_write_fee_history(history, create_backup=FEES_HISTORY_FILE.exists())


def migrate_fee_history():
    if not FEES_HISTORY_FILE.exists():
        return 0
    try:
        with open(FEES_HISTORY_FILE, "r", encoding="utf-8") as f:
            original = json.load(f)
        if not isinstance(original, list) or not original:
            raise ValueError("Fee history must be a non-empty list.")
        for record in original:
            if not isinstance(record, dict) or not isinstance(record.get("snapshot"), dict):
                raise ValueError("Each fee history record must contain a snapshot object.")
            snapshot = record["snapshot"]
            if not {"dph_percent", "kwh_fees", "fixed"}.issubset(snapshot):
                raise ValueError("Fee history snapshot is missing required pricing fields.")
            if not isinstance(snapshot.get("kwh_fees"), dict) or not isinstance(snapshot.get("fixed"), dict):
                raise ValueError("Fee history pricing fields must be objects.")
            if "prodej" in snapshot and not isinstance(snapshot["prodej"], dict):
                raise ValueError("Fee history prodej must be an object.")
            if "nakup" in snapshot and not isinstance(snapshot["nakup"], dict):
                raise ValueError("Fee history nakup must be an object.")
        _validate_fee_history(original)
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise RuntimeError(f"Fee history is invalid; refusing to overwrite {FEES_HISTORY_FILE}: {exc}") from exc

    migrated = []
    changed = 0
    for record in original:
        new_record = dict(record)
        snapshot = dict(record["snapshot"])
        sale = snapshot.get("prodej")
        if sale is None:
            sale = {}
        elif not isinstance(sale, dict):
            raise RuntimeError("Fee history contains an invalid prodej snapshot; refusing migration.")
        else:
            sale = dict(sale)
        purchase = snapshot.get("nakup")
        if purchase is None:
            purchase = {}
        elif not isinstance(purchase, dict):
            raise RuntimeError("Fee history contains an invalid nakup snapshot; refusing migration.")
        else:
            purchase = dict(purchase)
        before = json.dumps(snapshot, sort_keys=True, ensure_ascii=False)
        sale.setdefault("fixni_cena_enabled", False)
        sale.setdefault("fixni_cena", 0)
        purchase.setdefault("fixni_cena_enabled", False)
        purchase.setdefault("fixni_cena", 0)
        snapshot["prodej"] = sale
        snapshot["nakup"] = purchase
        new_record["snapshot"] = snapshot
        if json.dumps(snapshot, sort_keys=True, ensure_ascii=False) != before:
            changed += 1
        migrated.append(new_record)

    _validate_fee_history(migrated)
    if len(migrated) != len(original) or [r.get("effective_from") for r in migrated] != [r.get("effective_from") for r in original] or [r.get("effective_to") for r in migrated] != [r.get("effective_to") for r in original]:
        raise RuntimeError("Fee history migration changed period boundaries; refusing to write.")
    if changed:
        backup = _atomic_write_fee_history(migrated)
        with open(FEES_HISTORY_FILE, "r", encoding="utf-8") as f:
            written = json.load(f)
        _validate_fee_history(written)
        if written != migrated:
            raise RuntimeError("Fee history migration verification failed.")
        logger.info("Migrated %s fee history records; backup: %s", changed, backup)
    return changed

def ensure_fee_history(cfg, tzinfo):
    if FEES_HISTORY_FILE.exists():
        try:
            existing = load_fee_history()
            if not existing:
                raise ValueError("Stored fee history cannot be read.")
            _validate_fee_history(existing, require_snapshot_schema=False)
        except ValueError as exc:
            raise RuntimeError(f"Fee history is invalid; refusing to replace it: {exc}") from exc
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
    if current_record and current_record.get("snapshot") == snapshot:
        return history
    # Keep prior-day snapshots immutable; a configuration change takes effect today.
    today_record = next((record for record in history if record.get("effective_from") == today_str), None)
    if today_record:
        today_record["snapshot"] = snapshot
        today_record.pop("effective_to", None)
    else:
        if current_record:
            current_record["effective_to"] = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
        history.append({"effective_from": today_str, "snapshot": snapshot})
    history.sort(key=lambda x: x.get("effective_from", ""))
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
    if not isinstance(history_payload, list) or not history_payload:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="History cannot be empty.")
    current_history = load_fee_history()
    if FEES_HISTORY_FILE.exists():
        try:
            if not current_history:
                raise ValueError("Stored fee history cannot be read.")
            _validate_fee_history(current_history, require_snapshot_schema=False)
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=409, detail="Stored fee history is invalid; refusing to overwrite it.") from exc
    today = datetime.now(tzinfo).date()

    normalized_entries = []
    seen_dates = set()
    from pricing import normalize_fee_snapshot
    for entry in history_payload:
        if not isinstance(entry, dict):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Each fee history period must be an object.")
        date_str = entry.get("effective_from")
        if not date_str:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Each fee history period needs effective_from.")
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
        
        snapshot_raw = entry.get("snapshot")
        if not isinstance(snapshot_raw, dict) or not {"dph_percent", "kwh_fees", "fixed"}.issubset(snapshot_raw):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Each fee snapshot must contain dph_percent, kwh_fees and fixed.")
        if not isinstance(snapshot_raw.get("kwh_fees"), dict) or not isinstance(snapshot_raw.get("fixed"), dict):
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="Fee snapshot pricing fields must be objects.")
        snapshot = normalize_fee_snapshot(snapshot_raw)
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
    
    submitted_dates = [entry["effective_from"] for entry in normalized]
    if len(normalized) < len(current_history) or any(
        record.get("effective_from") not in submitted_dates for record in current_history
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Fee history update cannot remove existing periods.")
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

    def _normalize_value_format(item: dict[str, Any]) -> tuple[str | None, str | None, int | None]:
        value_format = item.get("value_format")
        if value_format is not None:
            value_format = str(value_format).strip().lower()
            if value_format not in {"default", "duration_seconds", "duration_minutes", "duration_hours"}:
                value_format = None

        duration_style = item.get("duration_style")
        if duration_style is not None:
            duration_style = str(duration_style).strip().lower()
            if duration_style not in {"short", "long"}:
                duration_style = None

        duration_max_parts_value = item.get("duration_max_parts")
        if duration_max_parts_value in (None, ""):
            duration_max_parts = None
        else:
            duration_max_parts = max(1, min(6, int(_safe_float(duration_max_parts_value) or 2)))

        return value_format, duration_style, duration_max_parts

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
        value_format, duration_style, duration_max_parts = _normalize_value_format(item)

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
                "value_format": value_format,
                "duration_style": duration_style,
                "duration_max_parts": duration_max_parts,
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
        value_format, duration_style, duration_max_parts = _normalize_value_format(item)

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
                "value_format": value_format,
                "duration_style": duration_style,
                "duration_max_parts": duration_max_parts,
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


def get_solar_overview_cfg(cfg):
    so = cfg.get("solar_overview") if isinstance(cfg.get("solar_overview"), dict) else None
    if so is None:
        so = {}
    weather_id = str(so.get("weather_entity_id") or "").strip()
    title = str(so.get("title") or "").strip()
    return {
        "enabled": True if so.get("enabled") is None else bool(so.get("enabled")),
        "weather_entity_id": weather_id or None,
        "title": title or None,
    }
