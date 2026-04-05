import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Dict, Optional
from api import get_local_tz, to_rfc3339

logger = logging.getLogger("uvicorn.error")

def _parse_energy_anchor(period: str, anchor: Optional[str], tzinfo) -> Optional[datetime]:
    if not anchor:
        return None
    try:
        if period == "month":
            return datetime.strptime(anchor, "%Y-%m").replace(tzinfo=tzinfo)
        if period == "year":
            return datetime.strptime(anchor, "%Y").replace(tzinfo=tzinfo)
        return datetime.fromisoformat(anchor.replace("Z", "+00:00")).astimezone(tzinfo)
    except ValueError:
        return None


def build_energy_balance_range(period: str, anchor: Optional[str], tzinfo) -> Dict[str, Any]:
    now_local = datetime.now(tzinfo)
    anchor_dt = _parse_energy_anchor(period, anchor, tzinfo) or now_local

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

def _parse_point_time(point: Dict[str, Any], tzinfo) -> Optional[datetime]:
    time_raw = point.get("time")
    if isinstance(time_raw, str):
        try:
            dt_local = datetime.fromisoformat(time_raw)
            if dt_local.tzinfo is None and tzinfo is not None:
                dt_local = dt_local.replace(tzinfo=tzinfo)
            return dt_local if tzinfo is None else dt_local.astimezone(tzinfo)
        except ValueError:
            pass

    time_utc_raw = point.get("time_utc")
    if isinstance(time_utc_raw, str):
        try:
            dt_utc = datetime.fromisoformat(time_utc_raw.replace("Z", "+00:00"))
            return dt_utc if tzinfo is None else dt_utc.astimezone(tzinfo)
        except ValueError:
            return None
    return None


def _power_value_to_kwh(value: float, interval_minutes: int) -> float:
    interval_hours = max(interval_minutes, 1) / 60.0
    # Home Assistant power entities are usually in W, but some setups store kW.
    if abs(value) <= 50:
        return value * interval_hours
    return (value / 1000.0) * interval_hours


def aggregate_power_points(
    points: List[Dict[str, Any]],
    interval_minutes: int = 15,
    *,
    bucket: str = "day",
    tzinfo=None,
) -> Dict[str, float]:
    totals: Dict[str, float] = {}
    for point in points or []:
        raw_value = point.get("value")
        if raw_value is None:
            continue
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue

        dt_local = _parse_point_time(point, tzinfo)
        if dt_local is None:
            continue

        if bucket == "month":
            key = dt_local.strftime("%Y-%m")
        else:
            key = dt_local.strftime("%Y-%m-%d")

        totals[key] = totals.get(key, 0.0) + _power_value_to_kwh(value, interval_minutes)

    return {key: round(value, 5) for key, value in totals.items()}
