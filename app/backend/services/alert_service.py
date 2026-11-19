import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uvicorn.error")

# The dashboard fetches today + tomorrow (include_neighbor_live=True); each day
# is 96 quarter-hour slots.
SLOTS_PER_DAY = 96

# User-facing Czech labels.  They are compared verbatim by the frontend, so
# keep the accents exactly as written here.
RECOMMENDATION_FIXED = "FIXNÍ CENA"
RECOMMENDATION_CHEAP = "SPOTŘEBUJTE NYNÍ"
RECOMMENDATION_EXPENSIVE = "ODLOŽTE SPOTŘEBU"
RECOMMENDATION_NORMAL = "BĚŽNÝ PROVOZ"


def _today_slots(prices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Slice of ``prices`` that belongs to today, for today-only min/max math."""
    if len(prices) > SLOTS_PER_DAY:
        return prices[:SLOTS_PER_DAY]
    return list(prices)


def _next_spot_slot(
    prices: List[Dict[str, Any]], current_slot: int
) -> Optional[Dict[str, Any]]:
    """First future slot priced from the spot market (fixed slots are skipped)."""
    for item in prices[current_slot + 1 :]:
        if not item.get("purchase_fixed"):
            return item
    return None


def _fixed_now_result(
    today_slots: List[Dict[str, Any]],
    current_slot: int,
    current_price: float,
) -> Dict[str, Any]:
    """Result for a slot whose purchase price is contractual/fixed.

    Shifting consumption cannot lower a fixed tariff, so the cheap/expensive
    advice stays neutral.  Today's min/max are still returned so the chart
    threshold annotations keep working.

    ``next_cheap_start`` only makes sense on a day that mixes fixed and spot
    slots; a flat fixed tariff yields ``None``.
    """
    today_finals = [p["final"] for p in today_slots]
    is_mixed_day = any(not p.get("purchase_fixed") for p in today_slots)
    next_spot = _next_spot_slot(today_slots, current_slot) if is_mixed_day else None
    return {
        "current_price": round(current_price, 2),
        "min_price_today": round(min(today_finals), 2),
        "max_price_today": round(max(today_finals), 2),
        "is_cheap_now": False,
        "is_expensive_now": False,
        "is_fixed_now": True,
        "next_cheap_start": next_spot["time"] if next_spot else None,
        "next_cheap_price": round(next_spot["final"], 2) if next_spot else None,
        "recommendation": RECOMMENDATION_FIXED,
    }


def get_price_alerts(
    prices: List[Dict[str, Any]],
    current_slot: int,
    tzinfo,
    low_threshold: float = 1.5,
    high_threshold: float = 5.0,
) -> Dict[str, Any]:
    """Analyse prices and generate the dashboard alert payload.

    ``prices`` may contain today followed by tomorrow (the dashboard fetches it
    with ``include_neighbor_live=True``).  Today-only metrics therefore stop at
    today's last slot; otherwise tomorrow's prices would leak into the "today"
    threshold bands and into the shift-consumption advice.
    """
    if not prices or not 0 <= current_slot < len(prices):
        return {}

    current_price_item = prices[current_slot]
    current_price = current_price_item["final"]
    today_slots = _today_slots(prices)

    if current_price_item.get("purchase_fixed"):
        return _fixed_now_result(today_slots, current_slot, current_price)

    future_prices = today_slots[current_slot:]
    if not future_prices:
        return {
            "current_price": round(current_price, 2),
            "is_fixed_now": False,
            "recommendation": RECOMMENDATION_NORMAL,
        }

    finals = [p["final"] for p in future_prices]
    min_price = min(finals)
    max_price = max(finals)

    is_cheap_now = current_price <= low_threshold
    is_expensive_now = current_price >= high_threshold

    next_cheap_slot = None
    if not is_cheap_now:
        for p in future_prices:
            if p.get("purchase_fixed"):
                continue
            if p["final"] <= low_threshold:
                next_cheap_slot = p
                break

    return {
        "current_price": round(current_price, 2),
        "min_price_today": round(min_price, 2),
        "max_price_today": round(max_price, 2),
        "is_cheap_now": is_cheap_now,
        "is_expensive_now": is_expensive_now,
        "is_fixed_now": False,
        "next_cheap_start": next_cheap_slot["time"] if next_cheap_slot else None,
        "next_cheap_price": round(next_cheap_slot["final"], 2) if next_cheap_slot else None,
        "recommendation": (
            RECOMMENDATION_CHEAP
            if is_cheap_now
            else (RECOMMENDATION_EXPENSIVE if is_expensive_now else RECOMMENDATION_NORMAL)
        ),
    }
