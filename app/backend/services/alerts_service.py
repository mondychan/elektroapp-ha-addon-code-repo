import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from services import alert_service
from config_loader import get_alerts_cfg

class AlertsService:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("uvicorn.error")

    def get_dashboard_alerts(self, cfg, tzinfo, get_prices_for_date_fn):
        now_local = datetime.now(tzinfo)
        today_str = now_local.strftime("%Y-%m-%d")
        
        # Získat ceny pro dnešek a zítřek
        prices = get_prices_for_date_fn(cfg, today_str, tzinfo, include_neighbor_live=True)
        
        current_slot = int((now_local.hour * 60 + now_local.minute) / 15)
        
        alerts_cfg = get_alerts_cfg(cfg)
        low_threshold = alerts_cfg.get("low_price_threshold", 1.5)
        high_threshold = alerts_cfg.get("high_price_threshold", 5.0)
        
        return alert_service.get_price_alerts(prices, current_slot, tzinfo, low_threshold, high_threshold)
