import time as time_module
from datetime import datetime, timedelta, timezone, time as datetime_time


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
