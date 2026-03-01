import os
import time as time_module
from datetime import datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo

from cache import should_use_daily_cache


def _to_date_str(date_obj):
    return date_obj.strftime("%Y-%m-%d")


def _complete_meta_for_date(date_obj, tzinfo):
    day_end_local = datetime.combine(date_obj + timedelta(days=1), datetime_time(0, 0), tzinfo)
    fetched_at = day_end_local.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {"fetched_at": fetched_at}


def _incomplete_meta_for_date(date_obj, tzinfo):
    day_end_local = datetime.combine(date_obj + timedelta(days=1), datetime_time(0, 0), tzinfo)
    fetched_at = (day_end_local.astimezone(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    return {"fetched_at": fetched_at}


def test_should_use_daily_cache_rejects_future_dates(tmp_path):
    tzinfo = ZoneInfo("Europe/Prague")
    future = datetime.now(tzinfo).date() + timedelta(days=1)
    cache_path = tmp_path / "future.json"
    cache_path.write_text("{}", encoding="utf-8")
    meta = _complete_meta_for_date(future, tzinfo)

    assert should_use_daily_cache(_to_date_str(future), cache_path, meta, tzinfo, ttl_seconds=600) is False


def test_should_use_daily_cache_uses_ttl_for_today(tmp_path):
    tzinfo = ZoneInfo("Europe/Prague")
    today = datetime.now(tzinfo).date()
    cache_path = tmp_path / "today.json"
    cache_path.write_text("{}", encoding="utf-8")

    assert should_use_daily_cache(_to_date_str(today), cache_path, {}, tzinfo, ttl_seconds=600) is True


def test_should_use_daily_cache_rejects_stale_today_cache(tmp_path):
    tzinfo = ZoneInfo("Europe/Prague")
    today = datetime.now(tzinfo).date()
    cache_path = tmp_path / "today-stale.json"
    cache_path.write_text("{}", encoding="utf-8")

    stale_ts = time_module.time() - 3600
    os.utime(cache_path, (stale_ts, stale_ts))

    assert should_use_daily_cache(_to_date_str(today), cache_path, {}, tzinfo, ttl_seconds=10) is False


def test_should_use_daily_cache_uses_completeness_for_historical_date(tmp_path):
    tzinfo = ZoneInfo("Europe/Prague")
    historical = datetime.now(tzinfo).date() - timedelta(days=2)
    cache_path = tmp_path / "historical.json"
    cache_path.write_text("{}", encoding="utf-8")
    meta = _complete_meta_for_date(historical, tzinfo)

    assert should_use_daily_cache(_to_date_str(historical), cache_path, meta, tzinfo, ttl_seconds=1) is True


def test_should_use_daily_cache_rejects_incomplete_historical_date(tmp_path):
    tzinfo = ZoneInfo("Europe/Prague")
    historical = datetime.now(tzinfo).date() - timedelta(days=2)
    cache_path = tmp_path / "historical-incomplete.json"
    cache_path.write_text("{}", encoding="utf-8")
    meta = _incomplete_meta_for_date(historical, tzinfo)

    assert should_use_daily_cache(_to_date_str(historical), cache_path, meta, tzinfo, ttl_seconds=600) is False
