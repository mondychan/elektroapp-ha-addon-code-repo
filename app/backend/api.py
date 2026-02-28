from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import HTTPException


def get_local_tz(tz_name):
    try:
        return ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return datetime.now().astimezone().tzinfo


def parse_time_range(date_str, start_str, end_str, tzinfo):
    if date_str:
        try:
            start_local = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=tzinfo)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc
        end_local = start_local + timedelta(days=1)
    elif start_str and end_str:
        try:
            start_local = datetime.fromisoformat(start_str)
            end_local = datetime.fromisoformat(end_str)
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail="Invalid start/end format. Use ISO 8601, e.g. 2026-01-15T00:00:00+01:00.",
            ) from exc
        if start_local.tzinfo is None:
            start_local = start_local.replace(tzinfo=tzinfo)
        if end_local.tzinfo is None:
            end_local = end_local.replace(tzinfo=tzinfo)
    else:
        now_local = datetime.now(tzinfo)
        start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def to_rfc3339(dt):
    return dt.isoformat().replace("+00:00", "Z")
