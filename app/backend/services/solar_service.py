import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

class SolarService:
    def __init__(
        self,
        get_forecast_solar_cfg_fn,
        safe_query_entity_last_value_fn,
        logger=None
    ):
        self.get_forecast_solar_cfg = get_forecast_solar_cfg_fn
        self.safe_query_entity_last_value = safe_query_entity_last_value_fn
        self.logger = logger or logging.getLogger("uvicorn.error")

    def get_solar_forecast(self, cfg):
        solar_cfg = self.get_forecast_solar_cfg(cfg)
        if not solar_cfg.get("enabled"):
            return {"enabled": False}

        res = {"enabled": True, "status": {}}
        
        entities = {
            "power_now": solar_cfg.get("power_now_entity_id"),
            "energy_current_hour": solar_cfg.get("energy_current_hour_entity_id"),
            "energy_next_hour": solar_cfg.get("energy_next_hour_entity_id"),
            "production_today": solar_cfg.get("energy_production_today_entity_id"),
            "production_today_remaining": solar_cfg.get("energy_production_today_remaining_entity_id"),
            "production_tomorrow": solar_cfg.get("energy_production_tomorrow_entity_id"),
            "peak_today": solar_cfg.get("power_highest_peak_time_today_entity_id"),
            "peak_tomorrow": solar_cfg.get("power_highest_peak_time_tomorrow_entity_id"),
        }

        for key, entity_id in entities.items():
            if entity_id:
                val = self.safe_query_entity_last_value(entity_id)
                res["status"][key] = val

        return res
