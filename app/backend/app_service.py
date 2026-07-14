import logging
import os
import asyncio
import atexit
import copy
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
    display_price_provider,
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
    get_solar_overview_cfg,
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
from services.dip_service import DIPService, DIPServiceError
from services.invoice_archive_service import InvoiceArchiveService
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
from services.recommendation_service import RecommendationService
from services.solar_overview_service import SolarOverviewService

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
DIP_CACHE_DIR = None
INVOICES_DIR = None
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
DIP_SERVICE: Optional[DIPService] = None
INVOICE_ARCHIVE_SERVICE: Optional[InvoiceArchiveService] = None

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
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    tmp_path.replace(path)
    if provider:
        meta_path = CACHE_DIR / f"prices-meta-{date_str}.json"
        fetched_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        meta_payload = {
            "cache_version": 2,
            "key": {"date": date_str, "provider": normalize_price_provider(provider)},
            "provider": normalize_price_provider(provider),
            "fetched_at": fetched_at,
            "complete_after": fetched_at,
            "source": "prices",
            "status": "complete",
        }
        tmp_meta_path = meta_path.with_suffix(meta_path.suffix + ".tmp")
        with open(tmp_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta_payload, f)
        tmp_meta_path.replace(meta_path)

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

def _pnd_to_points(day_payload: dict, tzinfo, *, kind: str) -> dict:
    """Convert one PND-normalized day (15-min intervals from the distributor's
    meter) into the same point shape returned by consumption/export services.

    kind == "consumption" -> use consumption_kwh (grid import / +A)
    kind == "export"       -> use production_kwh (grid export  / -A)
    """
    if kind == "export":
        pnd_key = "production_kwh"
        default_source = "pnd-export"
    elif kind == "consumption":
        pnd_key = "consumption_kwh"
        default_source = "pnd-consumption"
    else:
        raise ValueError(f"Unknown PND kind: {kind}")

    interval_minutes = int(day_payload.get("interval_minutes") or 15)
    points = []
    for iv in day_payload.get("intervals", []):
        val = iv.get(pnd_key)
        if val is None:
            continue
        ts_local = datetime.fromisoformat(iv["start"]).astimezone(tzinfo)
        ts_utc = ts_local.astimezone(timezone.utc)
        points.append(
            {
                "time": ts_local.isoformat(),
                "time_utc": to_rfc3339(ts_utc),
                "kwh_total": None,
                "kwh": val,
            }
        )

    date_str = day_payload.get("date")
    if date_str:
        start_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tzinfo)
        end_local = (start_local + timedelta(days=1)).replace(microsecond=0)
    else:
        start_local = points[0]["time"] if points else None
        end_local = None

    return {
        "range": {
            "start": to_rfc3339(start_local) if start_local else None,
            "end": to_rfc3339(end_local) if end_local else None,
        },
        "interval": f"{interval_minutes}m",
        "entity_id": day_payload.get("source") or default_source,
        "points": points,
        "tzinfo": tzinfo,
        "has_series": bool(points),
        "from_cache": False,
        "cache_fallback": False,
        "source": "pnd",
    }


def _pnd_day_points(cfg, date: str, *, kind: str) -> dict | None:
    """Return PND-backed points for a finalized day, or None if PND has no data."""
    if PND_SERVICE is None or not PND_SERVICE.has_day(date):
        return None
    try:
        result = PND_SERVICE.get_data(date, date)
    except Exception as exc:  # noqa: BLE001 - PND is best-effort; fall back to Influx
        logger.warning("PND data lookup failed for %s (%s): %s", date, kind, exc)
        return None
    days = result.get("days") or []
    if not days:
        return None
    day = days[0]
    intervals = day.get("intervals")
    if not intervals:
        return None
    # Read timezone directly from cfg — get_influx_cfg is strict about
    # requiring host/port/… and may raise; PND override doesn't need influx.
    tz_name = cfg.get("influxdb", {}).get("timezone", "Europe/Prague")
    tzinfo = get_local_tz(tz_name)
    return _pnd_to_points(day, tzinfo, kind=kind)


def get_consumption_points(cfg, date=None, start=None, end=None, cache_ttl=600):
    # PND override: once the distributor's finalized meter reading is synced
    # (nightly), use it instead of the live Influx sensor for that past day.
    if date and not start and not end:
        pnd_points = _pnd_day_points(cfg, date, kind="consumption")
        if pnd_points is not None:
            return pnd_points
    from services.consumption_service import get_consumption_points as gcp
    import sys
    class LegacyConsumptionCacheProxy:
        def load(self, d, k): return load_consumption_cache(d, k)
        def save(self, d, k, v): return save_consumption_cache(d, k, v)
    return gcp(cfg, sys.modules[__name__], LegacyConsumptionCacheProxy(), get_influx_cfg, get_local_tz, date, start, end, cache_ttl)

def get_export_points(cfg, date=None, start=None, end=None, cache_ttl=600):
    # PND override: finalized grid-export readings replace live Influx for past days.
    if date and not start and not end:
        pnd_points = _pnd_day_points(cfg, date, kind="export")
        if pnd_points is not None:
            return pnd_points
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
    get_influx_cfg=get_influx_cfg,
    get_energy_entities_cfg=get_energy_entities_cfg,
    parse_influx_interval_to_minutes=parse_influx_interval_to_minutes,
    query_entity_series=INFLUX_SERVICE.query_entity_series,
    aggregate_power_points=aggregate_power_points,
    logger=logger,
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
RECOMMENDATION_SERVICE = RecommendationService()

# --- Public API Functions (Compatibility) ---

def get_config():
    config = copy.deepcopy(load_config())
    for section_name in ("pnd", "dip"):
        section = config.get(section_name)
        if isinstance(section, dict):
            section.pop("password", None)
    return config


def _can_start_pnd_scheduler(cfg: Optional[dict[str, Any]] = None) -> bool:
    effective_cfg = cfg if isinstance(cfg, dict) else load_config()
    pnd_cfg = get_pnd_cfg(effective_cfg)
    return bool(pnd_cfg.get("enabled") and has_pnd_required_cfg(pnd_cfg))


def _can_start_dip_scheduler(cfg: Optional[dict[str, Any]] = None) -> bool:
    effective_cfg = cfg if isinstance(cfg, dict) else load_config()
    dip_cfg = effective_cfg.get("dip", {}) if isinstance(effective_cfg.get("dip"), dict) else {}
    return bool(dip_cfg.get("enabled") and dip_cfg.get("username") and dip_cfg.get("password"))

def save_config(new_config: dict = Body(...)):
    if isinstance(new_config, dict):
        current_config = load_config()
        for section_name in ("pnd", "dip"):
            section = new_config.get(section_name)
            current_section = current_config.get(section_name) if isinstance(current_config, dict) else None
            if isinstance(section, dict) and isinstance(current_section, dict):
                if not section.get("password") and current_section.get("password"):
                    section["password"] = current_section["password"]
        new_config["price_provider"] = normalize_price_provider(new_config.get("price_provider"))
        supervisor_options = {**new_config, "price_provider": display_price_provider(new_config.get("price_provider"))}
    else:
        supervisor_options = {}
    import yaml
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(new_config, f, allow_unicode=True)
    option_sync = save_options_sync(supervisor_options)
    try:
        supervisor_sync = SUPERVISOR_SERVICE.sync_addon_options(supervisor_options)
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
    if _can_start_dip_scheduler(new_config):
        start_dip_scheduler()
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
    global CONSUMPTION_CACHE, EXPORT_CACHE, PND_SERVICE, DIP_SERVICE, INVOICE_ARCHIVE_SERVICE
    if CONSUMPTION_CACHE_DIR:
        CONSUMPTION_CACHE = SeriesCache("consumption", CONSUMPTION_CACHE_DIR, 600)
    if EXPORT_CACHE_DIR:
        EXPORT_CACHE = SeriesCache("export", EXPORT_CACHE_DIR, 600)
    if PND_CACHE_DIR:
        PND_SERVICE = PNDService(PND_CACHE_DIR, logger=logger)
    if DIP_CACHE_DIR:
        DIP_SERVICE = DIPService(DIP_CACHE_DIR, logger=logger)
    if INVOICES_DIR:
        INVOICE_ARCHIVE_SERVICE = InvoiceArchiveService(INVOICES_DIR)

def get_cache_status():
    return {
        "prices": cache_status_for_dir(CACHE_DIR, "prices"),
        "consumption": CONSUMPTION_CACHE.get_status() if CONSUMPTION_CACHE else {},
        "export": EXPORT_CACHE.get_status() if EXPORT_CACHE else {},
        "pnd": PND_SERVICE.get_cache_status() if PND_SERVICE else {},
        "dip": DIP_SERVICE.get_status(load_config()) if DIP_SERVICE else {},
    }

def invalidate_cache(domain: str, date: str | None = None):
    domain = str(domain or "").strip().lower()
    valid_domains = {"prices", "consumption", "export", "pnd", "all"}
    if domain not in valid_domains:
        raise HTTPException(status_code=400, detail="Invalid cache domain.")

    removed = []

    def remove_path(path):
        if path and path.exists():
            path.unlink(missing_ok=True)
            removed.append(str(path))

    def remove_dir_files(path, pattern):
        if not path or not path.exists():
            return
        for item in path.glob(pattern):
            if item.is_file():
                item.unlink(missing_ok=True)
                removed.append(str(item))

    domains = {"prices", "consumption", "export", "pnd"} if domain == "all" else {domain}
    if "prices" in domains and CACHE_DIR:
        if date:
            clear_prices_cache_for_date(date, remove_files=True)
            removed.extend([str(CACHE_DIR / f"prices-{date}.json"), str(CACHE_DIR / f"prices-meta-{date}.json")])
        else:
            PRICES_CACHE.clear()
            PRICES_CACHE_PROVIDER.clear()
            remove_dir_files(CACHE_DIR, "prices-*.json")
            remove_dir_files(CACHE_DIR, "prices-meta-*.json")
    if "consumption" in domains and CONSUMPTION_CACHE_DIR:
        remove_path(CONSUMPTION_CACHE_DIR / f"consumption-{date}.json") if date else remove_dir_files(CONSUMPTION_CACHE_DIR, "consumption-*.json")
    if "export" in domains and EXPORT_CACHE_DIR:
        remove_path(EXPORT_CACHE_DIR / f"export-{date}.json") if date else remove_dir_files(EXPORT_CACHE_DIR, "export-*.json")
    if "pnd" in domains and PND_SERVICE:
        if date:
            remove_path(PND_SERVICE.normalized_dir / f"{date}.json")
        else:
            purge = PND_SERVICE.purge_cache()
            return {"ok": True, "domain": domain, "date": date, "removed": removed, "pnd": purge}

    return {"ok": True, "domain": domain, "date": date, "removed": removed}

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

def get_diagnostics(cfg=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    return {
        "version": APP_VERSION,
        "cache": get_cache_status(),
        "runtime": {
            "ote_backoff_seconds": get_ote_backoff_remaining_seconds(),
            "ote_unavailable": is_ote_unavailable(),
            "prefetch_scheduler_running": bool(RUNTIME_STATE.prefetch_thread and RUNTIME_STATE.prefetch_thread.is_alive()),
            "pnd_scheduler_running": bool(RUNTIME_STATE.pnd_thread and RUNTIME_STATE.pnd_thread.is_alive()),
            "dip_scheduler_running": bool(RUNTIME_STATE.dip_thread and RUNTIME_STATE.dip_thread.is_alive()),
        },
        "pnd": get_pnd_status(cfg=cfg) if PND_SERVICE else {"enabled": False, "configured": False},
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

def get_solar_overview(date=None, cfg=None):
    cfg = cfg if isinstance(cfg, dict) else load_config()
    return SOLAR_OVERVIEW_SERVICE.get_solar_overview(cfg, date)

SOLAR_OVERVIEW_SERVICE = SolarOverviewService(
    get_influx_cfg_fn=get_influx_cfg,
    get_energy_entities_cfg_fn=get_energy_entities_cfg,
    get_forecast_solar_cfg_fn=get_forecast_solar_cfg,
    get_solar_overview_cfg_fn=get_solar_overview_cfg,
    get_solar_forecast_fn=get_solar_forecast,
    query_entity_series_fn=INFLUX_SERVICE.query_entity_series,
    call_ha_service_fn=HOME_ASSISTANT_SERVICE.call_service,
    parse_influx_interval_to_minutes_fn=parse_influx_interval_to_minutes,
    get_local_tz_fn=get_local_tz,
    logger_instance=logger,
)

def get_recommendations(date=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    if not date:
        date = datetime.now(tzinfo).strftime("%Y-%m-%d")
    prices = get_prices(date=date, cfg=cfg, tzinfo=tzinfo).get("prices", [])
    schedule = get_schedule(duration=120, count=3, cfg=cfg, tzinfo=tzinfo)
    costs = get_costs(date=date, cfg=cfg, tzinfo=tzinfo)
    export = get_export(date=date, cfg=cfg, tzinfo=tzinfo)
    battery = get_battery(date=date, cfg=cfg, tzinfo=tzinfo)
    solar = get_solar_forecast(cfg=cfg)
    return RECOMMENDATION_SERVICE.build(
        date=date,
        prices=prices,
        schedule=schedule,
        battery=battery,
        solar=solar,
        costs=costs,
        export=export,
    )

def get_hp_data(period="day", anchor=None, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return HP_SERVICE.get_data(period=period, anchor=anchor, cfg=cfg, tzinfo=tzinfo)

def resolve_hp_entity(entity_id: str):
    return HP_SERVICE.resolve_entity(entity_id)

def preview_hp_discovery(payload: dict):
    return HP_SERVICE.resolve_effective_entities(payload)

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

def export_invoice_detail_csv(month: str, kind: str, cfg=None, tzinfo=None):
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    return EXPORT_DATA_SERVICE.generate_invoice_detail_csv(cfg, month, tzinfo, kind=kind)


def get_dip_status(cfg=None):
    if not DIP_SERVICE:
        return {"enabled": False, "configured": False, "profile_available": False}
    return DIP_SERVICE.get_status(cfg if isinstance(cfg, dict) else load_config())


def get_dip_profile(cfg=None):
    effective_cfg = cfg if isinstance(cfg, dict) else load_config()
    profile = DIP_SERVICE.get_profile() if DIP_SERVICE else {}
    manual = effective_cfg.get("supply_point", {}) if isinstance(effective_cfg.get("supply_point"), dict) else {}
    points = [dict(item) for item in profile.get("supply_points", []) if isinstance(item, dict)]
    consumption_ean = manual.get("consumption_ean")
    production_ean = manual.get("production_ean")
    if not points:
        if consumption_ean:
            points.append({"ean": consumption_ean, "kind": "Spotřeba", "technical": {}})
        if production_ean:
            points.append({"ean": production_ean, "kind": "Mikrozdroj", "technical": {}})
    primary = next((item for item in points if item.get("ean") == consumption_ean), points[0] if points else {})
    if primary:
        primary["customer_name"] = manual.get("customer_name") or primary.get("customer_name")
        primary["supply_address"] = manual.get("billing_address") or primary.get("supply_address")
        primary["mailing_address"] = manual.get("mailing_address") or primary.get("mailing_address")
        primary["supply_point_number"] = manual.get("supply_point_number") or primary.get("supply_point_number")
        technical = dict(primary.get("technical") or {})
        technical["meter_id"] = manual.get("meter_id") or technical.get("meter_id")
        technical["phases"] = manual.get("phases") or technical.get("phases")
        technical["breaker_amps"] = manual.get("breaker_amps") or technical.get("breaker_amps")
        technical["distribution_tariff"] = manual.get("distribution_tariff") or technical.get("distribution_tariff")
        primary["technical"] = technical
    return {**profile, "supply_points": points, "primary_supply_point": primary, "source": "dip+manual" if profile else "manual"}


def sync_dip(cfg=None):
    if not DIP_SERVICE:
        raise HTTPException(status_code=503, detail="DIP služba není inicializována.")
    try:
        return DIP_SERVICE.sync(cfg if isinstance(cfg, dict) else load_config())
    except DIPServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": exc.message, "details": exc.details}) from exc


def list_invoice_documents():
    return {"documents": INVOICE_ARCHIVE_SERVICE.list_documents() if INVOICE_ARCHIVE_SERVICE else []}


def store_invoice_document(filename: str, data: bytes):
    if not INVOICE_ARCHIVE_SERVICE:
        raise HTTPException(status_code=503, detail="Archiv faktur není inicializován.")
    try:
        return INVOICE_ARCHIVE_SERVICE.store(filename, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def delete_invoice_document(document_id: str):
    if not INVOICE_ARCHIVE_SERVICE or not INVOICE_ARCHIVE_SERVICE.delete(document_id):
        raise HTTPException(status_code=404, detail="Dokument nebyl nalezen.")
    return {"ok": True, "id": document_id}


def audit_invoice_document(document_id: str, cfg=None, tzinfo=None):
    if not INVOICE_ARCHIVE_SERVICE:
        raise HTTPException(status_code=503, detail="Archiv faktur není inicializován.")
    document = INVOICE_ARCHIVE_SERVICE.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Dokument nebyl nalezen.")
    parsed = document.get("parsed", {})
    period_from = parsed.get("period_from")
    period_to = parsed.get("period_to")
    if not period_from or not period_to or period_from[:7] != period_to[:7]:
        raise HTTPException(status_code=422, detail="Audit zatím vyžaduje fakturu v rámci jednoho kalendářního měsíce.")
    cfg, tzinfo = resolve_config_and_timezone(cfg, tzinfo)
    virtual_invoice = BILLING_SERVICE.compute_monthly_billing(cfg, period_from[:7], tzinfo, require_data=False)
    return INVOICE_ARCHIVE_SERVICE.audit(document_id, virtual_invoice)

def _invalidate_series_cache_for_day(date_str: str) -> None:
    """Drop stale Influx series-cache files for a day after its PND
    meter reading is synced (so billing/CSV reads PND, not Influx)."""
    if CONSUMPTION_CACHE:
        CONSUMPTION_CACHE.invalidate(date_str)
    if EXPORT_CACHE:
        EXPORT_CACHE.invalidate(date_str)


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
    today_str = datetime.now(tzinfo).strftime("%Y-%m-%d")
    tomorrow_str = (datetime.now(tzinfo) + timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Paralelní spuštění všech dashboardových dotazů
    tasks = [
        asyncio.to_thread(get_prices, date, cfg, tzinfo),
        asyncio.to_thread(get_prices, None, cfg, tzinfo),
        asyncio.to_thread(get_prices, today_str, cfg, tzinfo),
        asyncio.to_thread(get_prices, tomorrow_str, cfg, tzinfo),
        asyncio.to_thread(get_costs, date, None, None, cfg, tzinfo),
        asyncio.to_thread(get_export, date, None, None, cfg, tzinfo),
        asyncio.to_thread(get_battery, date, cfg, tzinfo),
        asyncio.to_thread(get_alerts, cfg, tzinfo),
        asyncio.to_thread(get_comparison, date, cfg, tzinfo),
        asyncio.to_thread(get_solar_forecast, cfg),
        asyncio.to_thread(get_recommendations, date, cfg, tzinfo),
        asyncio.to_thread(get_diagnostics, cfg),
        asyncio.to_thread(get_solar_overview, date, cfg),
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
        "overview_prices": safe_res(1, {}),
        "today_prices": safe_res(2, {}).get("prices", []),
        "tomorrow_prices": safe_res(3, {}).get("prices", []),
        "selected_date_prices": safe_res(0, {}).get("prices", []),
        "costs": safe_res(4, {}),
        "export": safe_res(5, {}),
        "battery": safe_res(6, {}),
        "alerts": safe_res(7, {}),
        "comparison": safe_res(8, {}),
        "solar": safe_res(9, {}),
        "recommendations": safe_res(10, {}),
        "diagnostics_summary": safe_res(11, {}),
        "solar_overview": safe_res(12, {"enabled": False}),
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
            invalidate_series_cache_fn=_invalidate_series_cache_for_day,
        ),
    )


def start_dip_scheduler():
    if not _can_start_dip_scheduler() or not DIP_SERVICE:
        logger.info("DIP scheduler not started because DIP is disabled or missing required credentials.")
        return False
    with RUNTIME_STATE.dip_thread_guard:
        if RUNTIME_STATE.dip_thread and RUNTIME_STATE.dip_thread.is_alive():
            return True
        RUNTIME_STATE.dip_stop_event.clear()

        def loop():
            first_run = True
            while not RUNTIME_STATE.dip_stop_event.is_set():
                cfg = load_config()
                dip_cfg = cfg.get("dip", {}) if isinstance(cfg.get("dip"), dict) else {}
                if not _can_start_dip_scheduler(cfg):
                    RUNTIME_STATE.dip_stop_event.wait(300)
                    continue
                should_sync = bool(dip_cfg.get("sync_enabled", True))
                if first_run and dip_cfg.get("verify_on_startup", True):
                    should_sync = True
                if should_sync:
                    try:
                        DIP_SERVICE.sync(cfg)
                    except DIPServiceError as exc:
                        logger.warning("DIP scheduled sync failed [%s]: %s", exc.code, exc.message)
                first_run = False
                interval_seconds = max(1, int(dip_cfg.get("sync_interval_hours", 24) or 24)) * 3600
                RUNTIME_STATE.dip_stop_event.wait(interval_seconds)

        RUNTIME_STATE.dip_thread = threading.Thread(target=loop, name="dip-scheduler", daemon=True)
        RUNTIME_STATE.dip_thread.start()
        return True

def log_cache_status():
    status = get_cache_status()
    logger.info("Prices cache: %s", status["prices"])
    logger.info("Consumption cache: %s", status["consumption"])

atexit.register(lambda: release_prefetch_process_lock(RUNTIME_STATE))
atexit.register(lambda: release_pnd_process_lock(RUNTIME_STATE))
atexit.register(lambda: RUNTIME_STATE.dip_stop_event.set())
