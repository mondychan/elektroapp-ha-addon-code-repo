import logging
import os
import asyncio
import atexit
from pathlib import Path
from datetime import datetime, timezone
from fastapi import Body, HTTPException, Query
from typing import Any, Dict, List, Optional

# Local imports
from api import get_local_tz, parse_time_range, to_rfc3339
from battery import average_recent_power
from billing import compute_fixed_breakdown_for_day
from influx import parse_influx_interval_to_minutes
from pricing import (
    get_price_provider,
    normalize_fee_snapshot,
    normalize_price_provider,
    calculate_sell_coefficient,
    is_price_cache_provider_match,
)
from cache import is_cache_fresh, is_date_cache_complete
import pricing
import threading

# New modules
from config_loader import (
    load_config,
    save_options_sync,
    save_fee_history,
    ensure_fee_history,
    get_fee_snapshot_for_date,
    resolve_config_and_timezone,
    update_fees_history_logic,
    get_influx_cfg,
    get_export_entity_id,
    get_battery_cfg,
    get_energy_entities_cfg,
    get_forecast_solar_cfg,
    get_pnd_cfg,
    get_hp_cfg,
    has_battery_required_cfg,
    has_pnd_required_cfg,
)
from services.runtime_state import RuntimeState
from services.cache_manager import SeriesCache, build_series_cache_key
from services.price_fetcher import (
    get_prices_for_date,
    build_price_map_for_date,
    get_spot_prices,
    apply_fee_snapshot,
    PRICES_CACHE,
    PRICES_CACHE_PROVIDER,
    get_ote_backoff_remaining_seconds,
    is_ote_unavailable,
)

from services.battery_projection import (
    build_hybrid_battery_projection,
    build_battery_projection,
    build_battery_history_points,
    get_last_non_null_value,
    iso_to_display_hhmm,
)
from services.energy_balance_service import (
    build_energy_balance_range,
    build_energy_balance_buckets,
    aggregate_hourly_from_price_entries,
    aggregate_hourly_from_kwh_points,
    aggregate_power_points,
)
from services.scheduler import (
    start_prefetch_scheduler as start_scheduler_fn,
    start_prefetch_scheduler,
    schedule_prefetch_loop,
    release_prefetch_process_lock,
    acquire_prefetch_process_lock,
    get_prefetch_lock_path,
    PREFETCH_LOCK_STALE_SECONDS,
)
from services.pnd_scheduler import (
    start_pnd_scheduler as start_pnd_scheduler_fn,
    schedule_pnd_loop,
    release_pnd_process_lock,
    acquire_pnd_process_lock,
    get_pnd_lock_path,
    PND_LOCK_STALE_SECONDS,
)
from services.pnd_service import PNDService, PNDServiceError
from services.supervisor_service import SupervisorService, SupervisorSyncError

# Re-exporting injected services (for main.py and others)
from services.influx_service import InfluxService
from services.home_assistant_service import HomeAssistantService
from services.hp_service import HPService
from services.prices_service import PricesService
from services.costs_service import CostsService
from services.export_service import ExportService
from services.billing_service import BillingService
from services.battery_service import BatteryService
from services.insights_service import InsightsService
from services.schedule_service import ScheduleService
from services.alerts_service import AlertsService
from services.comparison_service import ComparisonService
from services.solar_service import SolarService
from services.data_export_service import DataExportService

logger = logging.getLogger("uvicorn.error")
APP_VERSION = os.getenv("ADDON_VERSION", os.getenv("APP_VERSION", "dev"))

# Configuration and Paths (will be wired in main.py)
CONFIG_FILE = "config.yaml"
HA_OPTIONS_FILE = Path("/data/options.json")
STORAGE_DIR = None
CACHE_DIR = None
CONSUMPTION_CACHE_DIR = None
EXPORT_CACHE_DIR = None
PND_CACHE_DIR = None
OPTIONS_BACKUP_FILE = None
FEES_HISTORY_FILE = None

# Shared State
RUNTIME_STATE = RuntimeState()
INFLUX_SERVICE = InfluxService(logger=logger)
HOME_ASSISTANT_SERVICE = HomeAssistantService(logger=logger)
SUPERVISOR_SERVICE = SupervisorService(logger=logger)

# Cache Instances (initialized in main.py wiring)
CONSUMPTION_CACHE: Optional[SeriesCache] = None
EXPORT_CACHE: Optional[SeriesCache] = None
PND_SERVICE: Optional[PNDService] = None

# --- Price Cache Helpers ---
def load_prices_cache(date_str):
    if not CACHE_DIR: return None
    path = CACHE_DIR / f"prices-{date_str}.json"
    if not path.exists(): return None
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return None

def save_prices_cache(date_str, entries, provider=None):
    if not CACHE_DIR: return
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / f"prices-{date_str}.json"
    import json
    with open(path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    if provider:
        meta_path = CACHE_DIR / f"prices-meta-{date_str}.json"
        meta_payload = {
            "provider": normalize_price_provider(provider),
            "fetched_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f)

# Legacy aliases and constants for tests
CONSUMPTION_CACHE_TTL_SECONDS = 3600
EXPORT_CACHE_TTL_SECONDS = 3600

def build_consumption_cache_key(influx_cfg, entity_id=None, version=2):
    if entity_id is None:
        entity_id = influx_cfg.get("entity_id")
    return build_series_cache_key(influx_cfg, entity_id, version)

def build_export_cache_key(influx_cfg, entity_id=None, version=2):
    if entity_id is None:
        entity_id = influx_cfg.get("entity_id") or influx_cfg.get("export_entity_id")
    return build_series_cache_key(influx_cfg, entity_id, version)

def calculate_final_price(spot, hour, cfg, fee_snapshot):
    return pricing.calculate_final_price(spot, hour, cfg, fee_snapshot)

def normalize_dph_percent(value):
    return pricing.normalize_dph_percent(value)

def normalize_price_provider(value):
    return pricing.normalize_price_provider(value)

def parse_vt_periods(value):
    return pricing.parse_vt_periods(value)

def get_cached_price_provider(date_str):
    provider = PRICES_CACHE_PROVIDER.get(date_str)
    if provider: return provider
    if not CACHE_DIR: return "spot"
    meta_path = CACHE_DIR / f"prices-meta-{date_str}.json"
    if not meta_path.exists(): return "spot"
    try:
        import json
        with open(meta_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return normalize_price_provider(data.get("provider", "spot"))
    except: return "spot"

def has_price_cache(date_str, provider=None):
    cached = load_prices_cache(date_str)
    if not cached: return False
    if provider:
        return get_cached_price_provider(date_str) == normalize_price_provider(provider)
    return True

def is_price_cache_provider_match(date_str, provider, get_cached_price_provider_fn=None):
    if get_cached_price_provider_fn is None:
        get_cached_price_provider_fn = get_cached_price_provider
    from pricing import is_price_cache_provider_match as pricing_match
    return pricing_match(date_str, provider, get_cached_price_provider_fn)

def clear_prices_cache_for_date(date_str, remove_files=True):
    PRICES_CACHE.pop(date_str, None)
    PRICES_CACHE_PROVIDER.pop(date_str, None)
    if remove_files and CACHE_DIR:
        (CACHE_DIR / f"prices-{date_str}.json").unlink(missing_ok=True)
        (CACHE_DIR / f"prices-meta-{date_str}.json").unlink(missing_ok=True)

def get_prices_cache_path(date_str):
    if not CACHE_DIR: return None
    return CACHE_DIR / f"prices-{date_str}.json"

def get_prices_cache_meta_path(date_str):
    if not CACHE_DIR: return None
    return CACHE_DIR / f"prices-meta-{date_str}.json"

def load_prices_cache_meta(date_str):
    path = get_prices_cache_meta_path(date_str)
    if not path or not path.exists(): return None
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return None

def save_consumption_cache(date_str, key, data):
    if CONSUMPTION_CACHE:
        CONSUMPTION_CACHE.save(date_str, key, data)

def load_consumption_cache(date_str, key):
    if CONSUMPTION_CACHE:
        return CONSUMPTION_CACHE.load(date_str, key)
    return None, None, None

def save_export_cache(date_str, key, data):
    if EXPORT_CACHE:
        EXPORT_CACHE.save(date_str, key, data)

def load_export_cache(date_str, key):
    if EXPORT_CACHE:
        return EXPORT_CACHE.load(date_str, key)
    return None, None, None

def get_prefetch_lock_path_legacy(storage_dir=None):
    from services.scheduler import get_prefetch_lock_path as scheduler_get_path
    return scheduler_get_path(storage_dir or STORAGE_DIR)

def acquire_prefetch_process_lock_legacy(runtime_state=None, storage_dir=None):
    from services.scheduler import acquire_prefetch_process_lock as scheduler_acquire
    return scheduler_acquire(runtime_state or RUNTIME_STATE, storage_dir or STORAGE_DIR)

def release_prefetch_process_lock_legacy(runtime_state=None):
    from services.scheduler import release_prefetch_process_lock as scheduler_release
    return scheduler_release(runtime_state or RUNTIME_STATE)

def influx_query(influx, query):
    if INFLUX_SERVICE:
        return INFLUX_SERVICE.influx_query(influx, query)
    return None

# Exports for tests
get_prefetch_lock_path = get_prefetch_lock_path_legacy
acquire_prefetch_process_lock = acquire_prefetch_process_lock_legacy
release_prefetch_process_lock = release_prefetch_process_lock_legacy

def get_consumption_points(cfg, date=None, start=None, end=None, cache_ttl=600):
    from services.consumption_service import get_consumption_points as gcp
    import sys
    class LegacyConsumptionCacheProxy:
        def load(self, d, k): return load_consumption_cache(d, k)
        def save(self, d, k, v): return save_consumption_cache(d, k, v)
    return gcp(cfg, sys.modules[__name__], LegacyConsumptionCacheProxy(), get_influx_cfg, get_local_tz, date, start, end, cache_ttl)

def get_export_points(cfg, date=None, start=None, end=None, cache_ttl=600):
    from services.consumption_service import get_export_points as gep
    import sys
    class LegacyExportCacheProxy:
        def load(self, d, k): return load_export_cache(d, k)
        def save(self, d, k, v): return save_export_cache(d, k, v)
    return gep(cfg, sys.modules[__name__], LegacyExportCacheProxy(), get_influx_cfg, get_local_tz, get_export_entity_id, date, start, end, cache_ttl)

# --- Service Instances ---
PRICES_SERVICE = PricesService(
    get_prices_for_date=lambda cfg, d, tz, force_refresh=False, include_neighbor_live=False: get_prices_for_date(
        cfg, d, tz, 
        force_refresh=force_refresh, 
        include_neighbor_live=include_neighbor_live, 
        load_prices_cache_fn=load_prices_cache, 
        save_prices_cache_fn=save_prices_cache, 
        get_cached_price_provider_fn=get_cached_price_provider, 
        get_fee_snapshot_for_date_fn=get_fee_snapshot_for_date
    ),
    get_price_provider=get_price_provider,
    clear_prices_cache_for_date=clear_prices_cache_for_date,
)

COSTS_SERVICE = CostsService(
    get_consumption_points=lambda cfg, date=None, start=None, end=None: get_consumption_points(
        cfg, date=date, start=start, end=end
    ),
    build_price_map_for_date=lambda cfg, d, tz: build_price_map_for_date(
        cfg, d, tz, PRICES_SERVICE.get_prices
    ),
)

EXPORT_SERVICE = ExportService(
    get_export_points=lambda cfg, date=None, start=None, end=None: get_export_points(
        cfg, date=date, start=start, end=end
    ),
    build_price_map_for_date=lambda cfg, d, tz: build_price_map_for_date(
        cfg, d, tz, PRICES_SERVICE.get_prices
    ),
    get_fee_snapshot_for_date=get_fee_snapshot_for_date,
    calculate_sell_coefficient=calculate_sell_coefficient,
)

BILLING_SERVICE = BillingService(
    get_consumption_points=lambda cfg, date=None, start=None, end=None: get_consumption_points(
        cfg, date=date, start=start, end=end
    ),
    get_export_points=lambda cfg, date=None, start=None, end=None: get_export_points(
        cfg, date=date, start=start, end=end
    ),
    build_price_map_for_date=lambda cfg, d, tz: build_price_map_for_date(
        cfg, d, tz, PRICES_SERVICE.get_prices
    ),
    get_export_entity_id=get_export_entity_id,
    get_fee_snapshot_for_date=get_fee_snapshot_for_date,
    calculate_sell_coefficient=calculate_sell_coefficient,
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
    query_entity_series=INFLUX_SERVICE.query_entity_series,
    build_battery_history_points=build_battery_history_points,
    get_last_non_null_value=get_last_non_null_value,
    average_recent_power=average_recent_power,
    safe_query_entity_last_value=INFLUX_SERVICE.safe_query_entity_last_value,
    parse_influx_interval_to_minutes=parse_influx_interval_to_minutes,
    query_recent_slot_profile_by_day_type=lambda influx, eid, tz, target_date, days=28, interval="15m", measurement_candidates=None: 
        INFLUX_SERVICE.query_recent_slot_profile_by_day_type(influx, eid, tz, target_date, days, interval, measurement_candidates),
    build_hybrid_battery_projection=build_hybrid_battery_projection,
    build_battery_projection=lambda now, soc, avg, cfg, tz: build_battery_projection(
        now, soc, avg, cfg, tz, parse_influx_interval_to_minutes
    ),
    iso_to_display_hhmm=iso_to_display_hhmm,
    logger=logger,
)

INSIGHTS_SERVICE = InsightsService(
    get_influx_cfg=get_influx_cfg,
    get_energy_entities_cfg=get_energy_entities_cfg,
    build_energy_balance_range=build_energy_balance_range,
    parse_influx_interval_to_minutes=parse_influx_interval_to_minutes,
    query_entity_series=INFLUX_SERVICE.query_entity_series,
    aggregate_power_points=aggregate_power_points,
    build_energy_balance_buckets=build_energy_balance_buckets,
    get_prices_for_date=PRICES_SERVICE.get_prices,
    aggregate_hourly_from_price_entries=aggregate_hourly_from_price_entries,
    get_consumption_points=lambda cfg, date=None, start=None, end=None: get_consumption_points(
        cfg, date=date, start=start, end=end
    ),
    get_export_points=lambda cfg, date=None, start=None, end=None: get_export_points(
        cfg, date=date, start=start, end=end
    ),
    aggregate_hourly_from_kwh_points=aggregate_hourly_from_kwh_points,
    logger=logger,
)

SCHEDULE_SERVICE = ScheduleService(get_prices_for_date=PRICES_SERVICE.get_prices)

ALERTS_SERVICE = AlertsService(logger=logger)

COMPARISON_SERVICE = ComparisonService(logger=logger)

SOLAR_SERVICE = SolarService(
    get_influx_cfg_fn=get_influx_cfg,
    get_forecast_solar_cfg_fn=get_forecast_solar_cfg,
    safe_query_entity_last_value_fn=INFLUX_SERVICE.safe_query_entity_last_value,
    get_energy_entities_cfg_fn=get_energy_entities_cfg,
    query_entity_series_fn=INFLUX_SERVICE.query_entity_series,
    parse_influx_interval_to_minutes_fn=parse_influx_interval_to_minutes,
    aggregate_power_points_fn=aggregate_power_points,
    get_local_tz_fn=get_local_tz,
    history_file_path_fn=lambda: STORAGE_DIR / "solar-forecast-history.json" if STORAGE_DIR else None,
    logger=logger
)

HP_SERVICE = HPService(
    get_influx_cfg=get_influx_cfg,
    get_hp_cfg=get_hp_cfg,
    parse_time_range=parse_time_range,
    query_entity_series=INFLUX_SERVICE.query_entity_series,
    safe_query_entity_last_value=INFLUX_SERVICE.safe_query_entity_last_value,
    home_assistant_service=HOME_ASSISTANT_SERVICE,
    logger=logger,
)

EXPORT_DATA_SERVICE = DataExportService(billing_service=BILLING_SERVICE)

# --- Public API Functions (Compatibility) ---

def get_config():
    return load_config()


def _can_start_pnd_scheduler(cfg: Optional[dict[str, Any]] = None) -> bool:
    effective_cfg = cfg if isinstance(cfg, dict) else load_config()
    pnd_cfg = get_pnd_cfg(effective_cfg)
    return bool(pnd_cfg.get("enabled") and has_pnd_required_cfg(pnd_cfg))

def save_config(new_config: dict = Body(...)):
    if isinstance(new_config, dict):
        new_config["price_provider"] = normalize_price_provider(new_config.get("price_provider"))
    import yaml
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_config, f, allow_unicode=True)
    option_sync = save_options_sync(new_config if isinstance(new_config, dict) else {})
    try:
        supervisor_sync = SUPERVISOR_SERVICE.sync_addon_options(new_config if isinstance(new_config, dict) else {})
    except SupervisorSyncError as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {"detail": exc.detail}
        raise HTTPException(
            status_code=exc.status_code or 502,
            detail={
                "code": detail.get("code", "supervisor_sync_failed"),
                "message": exc.message,
                "supervisor_sync": detail,
            },
        ) from exc
    response = {"status": "ok", "message": "Konfigurace ulozena"}
    if option_sync:
        response["config_sync"] = option_sync
    if supervisor_sync:
        response["supervisor_sync"] = supervisor_sync
    if PND_SERVICE:
        pnd_cfg = get_pnd_cfg(new_config)
        if has_pnd_required_cfg(pnd_cfg):
            try:
                response["pnd_verify"] = PND_SERVICE.verify(pnd_cfg)
            except PNDServiceError as exc:
                PND_SERVICE.record_error(exc, job_type="config-verify")
                response["pnd_verify"] = {
                    "ok": False,
                    "code": exc.code,
                    "stage": exc.stage,
                    "message": exc.message,
                    "details": exc.details,
                }
            start_pnd_scheduler()
    return response

def get_fees_history(cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    history = ensure_fee_history(cfg, tzinfo)
    history.sort(key=lambda x: x.get("effective_from", ""))
    return {"history": history}

def update_fees_history(payload: dict = Body(...), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg=cfg, tzinfo=tzinfo)
    history = payload.get("history")
    if not isinstance(history, list):
        raise HTTPException(status_code=400, detail="Invalid history payload.")
    normalized = update_fees_history_logic(history, tzinfo)
    return {"history": normalized}

def finalize_initialization():
    global CONSUMPTION_CACHE, EXPORT_CACHE, PND_SERVICE
    if CONSUMPTION_CACHE_DIR:
        CONSUMPTION_CACHE = SeriesCache("consumption", CONSUMPTION_CACHE_DIR, 600)
    if EXPORT_CACHE_DIR:
        EXPORT_CACHE = SeriesCache("export", EXPORT_CACHE_DIR, 600)
    if PND_CACHE_DIR:
        PND_SERVICE = PNDService(PND_CACHE_DIR, logger=logger)

def get_cache_status():
    return {
        "prices": cache_status_for_dir(CACHE_DIR, "prices"),
        "consumption": CONSUMPTION_CACHE.get_status() if CONSUMPTION_CACHE else {},
        "export": EXPORT_CACHE.get_status() if EXPORT_CACHE else {},
        "pnd": PND_SERVICE.get_cache_status() if PND_SERVICE else {},
    }

def cache_status_for_dir(path, prefix):
    if not path or not path.exists(): return {"count": 0, "size_bytes": 0}
    import re
    files = [f for f in path.glob(f"{prefix}-*.json") if re.match(r"^\d{4}-\d{2}-\d{2}$", f.stem.replace(f"{prefix}-", ""))]
    files.sort()
    return {
        "dir": str(path),
        "count": len(files),
        "latest": files[-1].stem.replace(f"{prefix}-", "") if files else None,
        "size_bytes": sum(f.stat().st_size for f in files)
    }

def get_version(): return {"version": APP_VERSION}

def get_prices(date: str = Query(default=None), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    prices = PRICES_SERVICE.get_prices(cfg, date, tzinfo)
    return {"prices": prices}

def refresh_prices(payload: dict = Body(default=None), cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return PRICES_SERVICE.refresh_prices(payload=payload, cfg=cfg, tzinfo=tzinfo)

def get_consumption(date=None, start=None, end=None, cfg=None):
    cfg, _ = resolve_config_and_timezone(cfg)
    res = get_consumption_points(cfg, INFLUX_SERVICE, CONSUMPTION_CACHE, get_influx_cfg, get_local_tz, date, start, end)
    return { "range": res["range"], "points": res["points"], "interval": res["interval"], "entity_id": res["entity_id"] }

def get_costs(date=None, start=None, end=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return COSTS_SERVICE.get_costs(date=date, start=start, end=end, cfg=cfg, tzinfo=tzinfo)

def get_export(date=None, start=None, end=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return EXPORT_SERVICE.get_export(date=date, start=start, end=end, cfg=cfg, tzinfo=tzinfo)

def get_battery(date=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return BATTERY_SERVICE.get_battery(date=date, cfg=cfg, tzinfo=tzinfo)

def get_energy_balance(period="week", anchor=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return INSIGHTS_SERVICE.get_energy_balance(period=period, anchor=anchor, cfg=cfg, tzinfo=tzinfo)

def get_history_heatmap(month: str, metric="buy", cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return INSIGHTS_SERVICE.get_history_heatmap(month=month, metric=metric, cfg=cfg, tzinfo=tzinfo)

def get_schedule(duration=120, count=3, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return SCHEDULE_SERVICE.get_schedule(duration=duration, count=count, cfg=cfg, tzinfo=tzinfo)

def get_alerts(cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return ALERTS_SERVICE.get_dashboard_alerts(cfg, tzinfo, PRICES_SERVICE.get_prices)

def get_comparison(date=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    if not date:
        date = datetime.now(tzinfo).strftime("%Y-%m-%d")
    return COMPARISON_SERVICE.get_comparison(cfg, tzinfo, date, COSTS_SERVICE.get_costs)

def get_solar_forecast(cfg=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    return SOLAR_SERVICE.get_solar_forecast(cfg)

def get_hp_data(period="day", anchor=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return HP_SERVICE.get_data(period=period, anchor=anchor, cfg=cfg, tzinfo=tzinfo)

def resolve_hp_entity(entity_id: str):
    return HP_SERVICE.resolve_entity(entity_id)

def get_daily_summary(month: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return BILLING_SERVICE.get_daily_summary(month=month, cfg=cfg, tzinfo=tzinfo)

def get_billing_month(month: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return BILLING_SERVICE.get_billing_month(month=month, cfg=cfg, tzinfo=tzinfo)

def get_billing_year(year: int, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return BILLING_SERVICE.get_billing_year(year=year, cfg=cfg, tzinfo=tzinfo)

def export_monthly_csv(month: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return EXPORT_DATA_SERVICE.generate_monthly_csv(cfg, month, tzinfo)

def _require_pnd_service() -> PNDService:
    if not PND_SERVICE:
        raise HTTPException(status_code=503, detail="PND service neni inicializovana.")
    return PND_SERVICE

def _handle_pnd_error(exc: PNDServiceError):
    raise HTTPException(status_code=exc.status_code, detail=exc.to_detail())

def get_pnd_status(cfg=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    service = _require_pnd_service()
    return service.get_status(cfg=cfg, pnd_cfg=get_pnd_cfg(cfg))

def get_pnd_cache_status():
    return _require_pnd_service().get_cache_status()

def verify_pnd(cfg=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    pnd_cfg = get_pnd_cfg(cfg)
    service = _require_pnd_service()
    try:
        return service.verify(pnd_cfg)
    except PNDServiceError as exc:
        service.record_error(exc, job_type="verify")
        _handle_pnd_error(exc)

def backfill_pnd(range_name: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    pnd_cfg = get_pnd_cfg(cfg)
    service = _require_pnd_service()
    try:
        return service.backfill(pnd_cfg, range_name, tzinfo=tzinfo)
    except PNDServiceError as exc:
        service.record_error(exc, job_type="backfill", extra={"range": range_name})
        _handle_pnd_error(exc)

def get_pnd_data(from_date: str, to_date: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    service = _require_pnd_service()
    try:
        res = service.get_data(from_date, to_date)
        
        # Add local comparison
        energy_cfg = get_energy_entities_cfg(cfg)
        influx = get_influx_cfg(cfg)
        interval = influx.get("interval", "15m")
        interval_m = parse_influx_interval_to_minutes(interval, 15)
        
        start_local = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=tzinfo)
        end_local = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=tzinfo)
        
        local_data = {}
        for key, eid in [("consumption_kwh", energy_cfg.get("grid_import_power_entity_id")), 
                         ("production_kwh", energy_cfg.get("grid_export_power_entity_id"))]:
            if not eid: continue
            points = INFLUX_SERVICE.query_entity_series(
                influx, eid, start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc),
                interval=interval, tzinfo=tzinfo, numeric=True, measurement_candidates=["W", "kW"]
            )
            aggregated = aggregate_power_points(points, interval_m, bucket="day", tzinfo=tzinfo)
            for d_key, val in aggregated.items():
                local_data.setdefault(d_key, {})[key] = val
        
        for day in res.get("days", []):
            d_str = day.get("date")
            l_info = local_data.get(d_str, {})
            day["local_comparison"] = {
                "consumption_kwh": l_info.get("consumption_kwh"),
                "production_kwh": l_info.get("production_kwh"),
            }
        return res
    except PNDServiceError as exc:
        _handle_pnd_error(exc)

def purge_pnd_cache():
    return _require_pnd_service().purge_cache()

async def get_dashboard_snapshot(date=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    if not date:
        date = datetime.now(tzinfo).strftime("%Y-%m-%d")
    
    # Paralelní spuštění všech dashboardových dotazů
    tasks = [
        asyncio.to_thread(get_prices, date, cfg, tzinfo),
        asyncio.to_thread(get_costs, date, None, None, cfg, tzinfo),
        asyncio.to_thread(get_export, date, None, None, cfg, tzinfo),
        asyncio.to_thread(get_battery, date, cfg, tzinfo),
        asyncio.to_thread(get_alerts, cfg, tzinfo),
        asyncio.to_thread(get_comparison, date, cfg, tzinfo),
        asyncio.to_thread(get_solar_forecast, cfg),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Mapování výsledků (ošetření případných chyb)
    def safe_res(idx, default=None):
        res = results[idx]
        if isinstance(res, Exception):
            logger.error("Error in dashboard snapshot task %d: %s", idx, res)
            return default
        return res

    return {
        "prices": safe_res(0, {}),
        "costs": safe_res(1, {}),
        "export": safe_res(2, {}),
        "battery": safe_res(3, {}),
        "alerts": safe_res(4, {}),
        "comparison": safe_res(5, {}),
        "solar": safe_res(6, {}),
        "date": date,
        "version": APP_VERSION
    }

def start_prefetch_scheduler():
    return start_scheduler_fn(
        RUNTIME_STATE, STORAGE_DIR, 
        lambda: schedule_prefetch_loop(
            load_config, get_price_provider, resolve_config_and_timezone,
            has_price_cache, PRICES_SERVICE.get_prices
        )
    )

def start_pnd_scheduler():
    if not _can_start_pnd_scheduler():
        logger.info("PND scheduler not started because PND is disabled or missing required credentials.")
        return False
    return start_pnd_scheduler_fn(
        RUNTIME_STATE,
        STORAGE_DIR,
        lambda: schedule_pnd_loop(
            load_config_fn=load_config,
            resolve_config_and_timezone_fn=resolve_config_and_timezone,
            get_pnd_cfg_fn=get_pnd_cfg,
            has_pnd_required_cfg_fn=has_pnd_required_cfg,
            pnd_service=_require_pnd_service(),
        ),
    )

def log_cache_status():
    status = get_cache_status()
    logger.info("Prices cache: %s", status["prices"])
    logger.info("Consumption cache: %s", status["consumption"])

atexit.register(lambda: release_prefetch_process_lock(RUNTIME_STATE))
atexit.register(lambda: release_pnd_process_lock(RUNTIME_STATE))
