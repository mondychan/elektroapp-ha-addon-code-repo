import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn.error")

class ComparisonService:
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger("uvicorn.error")

    def get_comparison(self, cfg, tzinfo, today_str, get_costs_fn):
        """
        Srovnání dneška se včerejškem a minulým týdnem.
        """
        today_date = datetime.strptime(today_str, "%Y-%m-%d").date()
        yesterday_str = (today_date - timedelta(days=1)).strftime("%Y-%m-%d")
        last_week_str = (today_date - timedelta(days=7)).strftime("%Y-%m-%d")

        try:
            today_data = get_costs_fn(date=today_str, cfg=cfg, tzinfo=tzinfo)
            yesterday_data = get_costs_fn(date=yesterday_str, cfg=cfg, tzinfo=tzinfo)
            last_week_data = get_costs_fn(date=last_week_str, cfg=cfg, tzinfo=tzinfo)
            
            today_total = today_data.get("summary", {}).get("cost_total", 0)
            yesterday_total = yesterday_data.get("summary", {}).get("cost_total", 0)
            last_week_total = last_week_data.get("summary", {}).get("cost_total", 0)
            
            today_kwh = today_data.get("summary", {}).get("kwh_total", 0)
            yesterday_kwh = yesterday_data.get("summary", {}).get("kwh_total", 0)
            last_week_kwh = last_week_data.get("summary", {}).get("kwh_total", 0)

            return {
                "today": {"cost": today_total, "kwh": today_kwh},
                "yesterday": {
                    "cost": yesterday_total, 
                    "kwh": yesterday_kwh,
                    "diff_cost_pct": self._calc_diff(today_total, yesterday_total),
                    "diff_kwh_pct": self._calc_diff(today_kwh, yesterday_kwh)
                },
                "last_week": {
                    "cost": last_week_total, 
                    "kwh": last_week_kwh,
                    "diff_cost_pct": self._calc_diff(today_total, last_week_total),
                    "diff_kwh_pct": self._calc_diff(today_kwh, last_week_kwh)
                }
            }
        except Exception as exc:
            self.logger.error("Error in comparison service: %s", exc)
            return {}

    def _calc_diff(self, current, previous):
        if not previous or previous == 0:
            return 0
        return round(((current - previous) / previous) * 100, 1)
