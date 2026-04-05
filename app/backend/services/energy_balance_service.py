import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Dict, Optional
from api import get_local_tz, to_rfc3339

logger = logging.getLogger("uvicorn.error")

def build_energy_balance_range(period: str, anchor: Optional[str], tzinfo) -> Dict[str, Any]:
    now_local = datetime.now(tzinfo)
    if anchor:
        try:
            anchor_dt = datetime.fromisoformat(anchor.replace("Z", "+00:00")).astimezone(tzinfo)
        except ValueError:
            anchor_dt = now_local
    else:
        anchor_dt = now_local

    if period == "month":
        start_local = anchor_dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if start_local.month == 12:
            end_local = start_local.replace(year=start_local.year + 1, month=1)
        else:
            end_local = start_local.replace(month=start_local.month + 1)
        bucket = "day"
    elif period == "year":
        start_local = anchor_dt.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local.replace(year=start_local.year + 1)
        bucket = "month"
    else:  # week
        start_local = (anchor_dt - timedelta(days=anchor_dt.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=7)
        bucket = "day"

    return {
        "period": period,
        "anchor": anchor,
        "bucket": bucket,
        "start_local": start_local,
        "end_local": end_local,
        "start_utc": start_local.astimezone(timezone.utc),
        "end_utc": end_local.astimezone(timezone.utc),
    }

def build_energy_balance_buckets(range_info: Dict[str, Any], tzinfo) -> List[Dict[str, Any]]:
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

def aggregate_hourly_from_price_entries(entries: List[Dict[str, Any]]) -> List[Optional[float]]:
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

def aggregate_hourly_from_kwh_points(points: List[Dict[str, Any]]) -> List[Optional[float]]:
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

def aggregate_power_points(points: List[Dict[str, Any]]) -> Optional[float]:
    values = [p["value"] for p in points if p.get("value") is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 5)
