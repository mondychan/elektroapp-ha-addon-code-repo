import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

def get_price_alerts(prices: List[Dict[str, Any]], current_slot: int, tzinfo, low_threshold: float = 1.5, high_threshold: float = 5.0) -> Dict[str, Any]:
    """
    Analýza cen a generování alertů pro frontend.
    prices: Seznam cenových bodů (dnešek + zítřek).
    """
    if not prices:
        return {}

    now = datetime.now(tzinfo)
    current_hour = now.hour
    current_minute = now.minute
    
    # Najít aktuální cenu
    current_price_item = None
    if 0 <= current_slot < len(prices):
        current_price_item = prices[current_slot]
    
    if not current_price_item:
        return {}

    current_price = current_price_item["final"]
    
    # Budoucí ceny (včetně aktuální)
    future_prices = prices[current_slot:]
    if not future_prices:
        return {"current_price": current_price}

    finals = [p["final"] for p in future_prices]
    min_price = min(finals)
    max_price = max(finals)
    avg_price = sum(finals) / len(finals)
    
    # Najít nejlevnější slot v budoucnu
    min_item = next(p for p in future_prices if p["final"] == min_price)
    
    # Identifikace levných oken (např. pod 20% percentil nebo pod fixní práh)
    # Pro jednoduchost: levné = pod 110% minima nebo pod průměrem - 20%
    # Použít konfigurované prahy, nebo vypočtené dynamicky pokud jsou výhodnější
    is_cheap_now = current_price <= low_threshold
    is_expensive_now = current_price >= high_threshold
    
    # Najít kdy začíná další levné okno (pokud teď není levno)
    next_cheap_slot = None
    if not is_cheap_now:
        for p in future_prices:
            if p["final"] <= low_threshold:
                next_cheap_slot = p
                break
    
    return {
        "current_price": round(current_price, 2),
        "min_price_today": round(min_price, 2),
        "max_price_today": round(max_price, 2),
        "is_cheap_now": is_cheap_now,
        "is_expensive_now": is_expensive_now,
        "next_cheap_start": next_cheap_slot["time"] if next_cheap_slot else None,
        "next_cheap_price": round(next_cheap_slot["final"], 2) if next_cheap_slot else None,
        "recommendation": "SPOTŘEBUJTE NYNÍ" if is_cheap_now else ("ODLOŽTE SPOTŘEBU" if is_expensive_now else "BĚŽNÝ PROVOZ")
    }
