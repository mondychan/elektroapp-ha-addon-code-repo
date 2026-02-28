from datetime import datetime


def average_recent_power(points):
    values = [p.get("value") for p in points if isinstance(p, dict) and p.get("value") is not None]
    if not values:
        return None
    return sum(values) / len(values)


def get_slot_index_for_dt(dt):
    return dt.hour * 4 + (dt.minute // 15)


def build_slot_avg_profile(points, tzinfo=None):
    slot_buckets = {}
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
        if tzinfo:
            if dt_local.tzinfo is None:
                dt_local = dt_local.replace(tzinfo=tzinfo)
            else:
                dt_local = dt_local.astimezone(tzinfo)
        slot = get_slot_index_for_dt(dt_local)
        bucket = slot_buckets.setdefault(slot, [])
        bucket.append(float(value))
    profile = {}
    for slot, values in slot_buckets.items():
        if values:
            profile[slot] = sum(values) / len(values)
    return profile
