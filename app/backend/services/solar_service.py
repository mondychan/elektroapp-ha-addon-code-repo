import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

class SolarService:
    def __init__(
        self,
        get_influx_cfg_fn,
        get_forecast_solar_cfg_fn,
        safe_query_entity_last_value_fn,
        logger=None
    ):
        self.get_influx_cfg = get_influx_cfg_fn
        self.get_forecast_solar_cfg = get_forecast_solar_cfg_fn
        self.safe_query_entity_last_value = safe_query_entity_last_value_fn
        self.logger = logger or logging.getLogger("uvicorn.error")

    def get_solar_forecast(self, cfg):
        solar_cfg = self.get_forecast_solar_cfg(cfg)
        influx = self.get_influx_cfg(cfg)
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
                is_numeric = "peak" not in key
                val = self.safe_query_entity_last_value(influx, entity_id, numeric=is_numeric, label=f"solar_{key}")
                if val:
                    res["status"][key] = val.get("value") if is_numeric else val.get("raw_value")
                else:
                    res["status"][key] = None

        return res
