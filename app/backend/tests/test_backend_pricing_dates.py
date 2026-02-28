from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import pytest
from fastapi import HTTPException


def test_normalize_dph_percent_accepts_percent_and_multiplier(backend_main):
    assert backend_main.normalize_dph_percent(21) == 21
    assert backend_main.normalize_dph_percent(1.21) == pytest.approx(21)
    assert backend_main.normalize_dph_percent(0) == 0.0


def test_calculate_final_price_respects_vt_and_nt_fees(backend_main):
    cfg = {"tarif": {"vt_periods": [[6, 7]]}}
    fee_snapshot = {
        "dph_percent": 21,
        "kwh_fees": {
            "komodita_sluzba": 0.1,
            "oze": 0.2,
            "dan": 0.3,
            "systemove_sluzby": 0.4,
            "distribuce": {"NT": 0.5, "VT": 1.5},
        },
    }

    vt_price = backend_main.calculate_final_price(2.0, 6, cfg, fee_snapshot)
    nt_price = backend_main.calculate_final_price(2.0, 8, cfg, fee_snapshot)

    assert vt_price == round((2.0 + 0.1 + 0.2 + 0.3 + 0.4 + 1.5) * 1.21, 5)
    assert nt_price == round((2.0 + 0.1 + 0.2 + 0.3 + 0.4 + 0.5) * 1.21, 5)


def test_parse_time_range_from_date_string_returns_utc_boundaries(backend_main):
    tzinfo = ZoneInfo("Europe/Prague")
    start_utc, end_utc = backend_main.parse_time_range("2026-01-15", None, None, tzinfo)

    # Winter in Prague is UTC+1.
    assert start_utc.isoformat() == "2026-01-14T23:00:00+00:00"
    assert end_utc.isoformat() == "2026-01-15T23:00:00+00:00"


def test_parse_time_range_invalid_date_raises_400(backend_main):
    tzinfo = ZoneInfo("Europe/Prague")
    with pytest.raises(HTTPException) as exc_info:
        backend_main.parse_time_range("2026-99-99", None, None, tzinfo)
    assert exc_info.value.status_code == 400
    assert "Invalid date format" in exc_info.value.detail


def test_is_date_cache_complete_checks_day_end_in_timezone(backend_main):
    tzinfo = ZoneInfo("Europe/Prague")
    date_str = "2026-01-15"

    incomplete_meta = {"fetched_at": "2026-01-15T22:59:59Z"}
    complete_meta = {"fetched_at": "2026-01-15T23:00:00Z"}

    assert backend_main.is_date_cache_complete(date_str, incomplete_meta, tzinfo) is False
    assert backend_main.is_date_cache_complete(date_str, complete_meta, tzinfo) is True


def test_compute_fixed_breakdown_for_day_applies_dph_and_month_split(backend_main):
    snapshot = {
        "dph_percent": 21,
        "fixed": {
            "daily": {"staly_plat": 10.0},
            "monthly": {"jistic": 310.0},
        },
    }

    daily, monthly = backend_main.compute_fixed_breakdown_for_day(snapshot, 31)
    assert daily["staly_plat"] == 12.1
    assert monthly["jistic"] == pytest.approx((310.0 / 31.0) * 1.21)


def test_parse_time_range_with_naive_start_end_uses_given_timezone(backend_main):
    tzinfo = ZoneInfo("Europe/Prague")
    start_utc, end_utc = backend_main.parse_time_range(
        None, "2026-02-01T00:00:00", "2026-02-01T02:00:00", tzinfo
    )

    assert start_utc == datetime(2026, 1, 31, 23, 0, tzinfo=timezone.utc)
    assert end_utc == datetime(2026, 2, 1, 1, 0, tzinfo=timezone.utc)
