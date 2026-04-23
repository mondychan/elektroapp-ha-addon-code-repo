import logging
from datetime import datetime, timezone
from fastapi import HTTPException
from requests import RequestException
from api import parse_time_range, to_rfc3339
from services.cache_manager import build_series_cache_key, SeriesCache
from cache import should_use_daily_cache
from influx import (
    build_influx_from_clause_for_measurement,
    escape_influx_tag_value,
    quote_influx_identifier,
    validate_influx_interval,
)

logger = logging.getLogger("uvicorn.error")

def get_consumption_points(
    cfg, 
    influx_service, 
    consumption_cache: SeriesCache,
    get_influx_cfg_fn,
    get_total_tz_fn,
    date=None, 
    start=None, 
    end=None,
    cache_ttl=600
):
    influx = get_influx_cfg_fn(cfg)
    tzinfo = get_total_tz_fn(influx.get("timezone"))
    
    cache_key = None
    cached = None
    cache_path = None
    cache_meta = None
    
    if date and not start and not end:
        cache_key = build_series_cache_key(influx, influx.get("entity_id"))
        cached, cache_path, cache_meta = consumption_cache.load(date, cache_key)
        if cached and should_use_daily_cache(date, cache_path, cache_meta, tzinfo, cache_ttl):
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = False
            return cached

    start_utc, end_utc = parse_time_range(date, start, end, tzinfo)

    from_clause = build_influx_from_clause_for_measurement(influx, influx["measurement"])
    field = quote_influx_identifier(influx["field"])
    entity_id = influx["entity_id"]
    interval = validate_influx_interval(influx.get("interval", "15m"))

    q = (
        f'SELECT last({field}) AS "kwh_total" '
        f"FROM {from_clause} "
        f"WHERE time >= '{to_rfc3339(start_utc)}' AND time < '{to_rfc3339(end_utc)}' "
        f'AND "entity_id"=\'{escape_influx_tag_value(entity_id)}\' '
        f"GROUP BY time({interval}) fill(null)"
    )

    try:
        data = influx_service.influx_query(influx, q)
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
            kwh = total if ts == start_utc_ts else None
        else:
            diff = total - prev_total
            if diff >= 0:
                kwh = diff
            else:
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
        consumption_cache.save(date, cache_key, cache_payload)
    return result

def get_export_points(
    cfg, 
    influx_service, 
    export_cache: SeriesCache,
    get_influx_cfg_fn,
    get_total_tz_fn,
    get_export_entity_id_fn,
    date=None, 
    start=None, 
    end=None,
    cache_ttl=600
):
    influx = get_influx_cfg_fn(cfg)
    tzinfo = get_total_tz_fn(influx.get("timezone"))
    export_entity_id = get_export_entity_id_fn(cfg)
    if not export_entity_id:
        raise HTTPException(status_code=500, detail="Missing influxdb export_entity_id.")
    
    cache_key = None
    cached = None
    cache_path = None
    cache_meta = None
    
    if date and not start and not end:
        cache_key = build_series_cache_key(influx, export_entity_id)
        cached, cache_path, cache_meta = export_cache.load(date, cache_key)
        if cached and should_use_daily_cache(date, cache_path, cache_meta, tzinfo, cache_ttl):
            cached["tzinfo"] = tzinfo
            cached["from_cache"] = True
            cached["cache_fallback"] = False
            return cached

    start_utc, end_utc = parse_time_range(date, start, end, tzinfo)

    from_clause = build_influx_from_clause_for_measurement(influx, influx["measurement"])
    field = quote_influx_identifier(influx["field"])
    interval = validate_influx_interval(influx.get("interval", "15m"))

    q = (
        f'SELECT last({field}) AS "kwh_total" '
        f"FROM {from_clause} "
        f"WHERE time >= '{to_rfc3339(start_utc)}' AND time < '{to_rfc3339(end_utc)}' "
        f'AND "entity_id"=\'{escape_influx_tag_value(export_entity_id)}\' '
        f"GROUP BY time({interval}) fill(null)"
    )

    try:
        data = influx_service.influx_query(influx, q)
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
        export_cache.save(date, cache_key, cache_payload)
    return result
