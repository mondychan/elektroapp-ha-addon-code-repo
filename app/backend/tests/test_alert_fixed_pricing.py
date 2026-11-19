from zoneinfo import ZoneInfo

from services import alert_service
from services.alert_service import get_price_alerts
from services.schedule_service import ScheduleService

PRAGUE = ZoneInfo("Europe/Prague")


def slot(index: int, final: float, fixed=None) -> dict:
    item = {"time": "%02d:%02d" % (index // 4, (index % 4) * 15), "final": final}
    if fixed is not None:
        item["purchase_fixed"] = fixed
    return item


def spot_day(price: float = 3.0) -> list:
    return [slot(i, price, False) for i in range(96)]


def fixed_day(price: float = 7.35) -> list:
    return [slot(i, price, True) for i in range(96)]


def test_fixed_purchase_is_reported_as_fixed_and_never_cheap_or_expensive():
    result = get_price_alerts(fixed_day(7.9), 40, PRAGUE)

    assert result["is_fixed_now"] is True
    assert result["is_cheap_now"] is False
    assert result["is_expensive_now"] is False
    assert result["recommendation"] == alert_service.RECOMMENDATION_FIXED
    assert result["current_price"] == 7.9
    assert result["min_price_today"] == 7.9
    assert result["max_price_today"] == 7.9


def test_fixed_purchase_has_no_next_cheap_window():
    # A flat fixed tariff is identical in every slot, so advertising a "next
    # cheap window" would be misleading.
    result = get_price_alerts(fixed_day(), 10, PRAGUE)

    assert result["next_cheap_start"] is None
    assert result["next_cheap_price"] is None


def test_tomorrow_prices_do_not_leak_into_today_metrics():
    today = [slot(i, 3.0, False) for i in range(96)]
    tomorrow = [slot(i, 0.01, False) for i in range(96)]
    result = get_price_alerts(today + tomorrow, 10, PRAGUE)

    assert result["min_price_today"] == 3.0
    assert result["next_cheap_start"] is None
    assert result["is_cheap_now"] is False


def test_next_cheap_window_is_found_later_today():
    prices = [slot(i, 6.0 if i < 50 else 0.5, False) for i in range(96)]
    result = get_price_alerts(prices, 10, PRAGUE)

    assert result["next_cheap_start"] == "12:30"
    assert result["next_cheap_price"] == 0.5


def test_spot_now_below_low_threshold_is_cheap():
    result = get_price_alerts(spot_day(1.0), 10, PRAGUE)

    assert result["is_cheap_now"] is True
    assert result["is_expensive_now"] is False
    assert result["is_fixed_now"] is False
    assert result["recommendation"] == alert_service.RECOMMENDATION_CHEAP


def test_spot_now_above_high_threshold_is_expensive():
    result = get_price_alerts(spot_day(6.4), 10, PRAGUE)

    assert result["is_cheap_now"] is False
    assert result["is_expensive_now"] is True
    assert result["recommendation"] == alert_service.RECOMMENDATION_EXPENSIVE


def test_boundaries_and_invalid_payloads():
    assert get_price_alerts([], 0, PRAGUE) == {}
    assert get_price_alerts(None, 0, PRAGUE) == {}
    assert get_price_alerts(spot_day(3.0), 96, PRAGUE) == {}
    assert get_price_alerts(spot_day(3.0), -1, PRAGUE) == {}


def test_last_slot_today_does_not_use_tomorrow():
    today = [slot(i, 9.0, False) for i in range(96)]
    tomorrow = [slot(i, 0.1, False) for i in range(96)]
    result = get_price_alerts(today + tomorrow, 95, PRAGUE)

    assert result["min_price_today"] == 9.0
    assert result["next_cheap_start"] is None


def test_mixed_day_fixed_now_points_to_later_spot_window():
    prices = [slot(i, 7.0, True) for i in range(96)]
    prices[60:] = [slot(i, 0.8, False) for i in range(60, 96)]
    result = get_price_alerts(prices, 20, PRAGUE)

    assert result["is_fixed_now"] is True
    assert result["next_cheap_start"] == "15:00"


def test_schedule_fixed_tariff_is_annotated_and_ordered():
    service = ScheduleService(get_prices_for_date=None)

    def fake_get_prices(cfg, date_str, tzinfo):
        return [
            {
                "time": "%s %02d:%02d" % (date_str, i // 4, (i % 4) * 15),
                "final": 7.35,
                "purchase_fixed": True,
            }
            for i in range(96)
        ]

    service._get_prices_for_date = fake_get_prices
    result = service.get_schedule(duration=60, count=2, cfg={}, tzinfo=PRAGUE)

    assert result["duration"] == 60
    assert len(result["recommendations"]) == 2
    assert result["note"] is not None
    starts = [rec["start"] for rec in result["recommendations"]]
    assert starts == sorted(starts)
