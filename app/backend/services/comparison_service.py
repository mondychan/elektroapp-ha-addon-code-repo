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
        Pokud je 'today_str' dnešní datum, srovnáváme stejný časový úsek (např. do 11:00).
        """
        now_local = datetime.now(tzinfo)
        today_date = datetime.strptime(today_str, "%Y-%m-%d").date()
        is_today = today_date == now_local.date()
        
        yesterday_date = today_date - timedelta(days=1)
        last_week_date = today_date - timedelta(days=7)

        # Základní parametry pro dnešek
        today_params = {"date": today_str, "cfg": cfg, "tzinfo": tzinfo}
        
        # Pokud srovnáváme dnešek, chceme srovnávat stejný časový úsek u včerejška a min. týdne
        prev_params_extra = {}
        if is_today:
            # Čas od půlnoci do teď
            current_time_str = now_local.strftime("%H:%M:%S")
            prev_params_extra = {
                "start": "00:00:00", # get_costs_fn v CostsService si k tomu přidá datum
                "end": current_time_str
            }
            # Poznámka: CostsService.get_costs (resp IndexService) bere start/end jako ISO nebo k nim přidá datum.
            # Musíme víc prozkoumat CostsService.get_costs. 
            # V app_service.py je get_costs(date=, start=, end=, ...)
            # Pokud pošleme start a end, musíme poslat i date aby věděl který den.
        
        try:
            today_data = get_costs_fn(**today_params)
            
            yesterday_params = {"date": yesterday_date.strftime("%Y-%m-%d"), "cfg": cfg, "tzinfo": tzinfo}
            if is_today:
                yesterday_params["start"] = yesterday_params["date"] + "T00:00:00"
                yesterday_params["end"] = yesterday_params["date"] + "T" + now_local.strftime("%H:%M:%S")

            last_week_params = {"date": last_week_date.strftime("%Y-%m-%d"), "cfg": cfg, "tzinfo": tzinfo}
            if is_today:
                last_week_params["start"] = last_week_params["date"] + "T00:00:00"
                last_week_params["end"] = last_week_params["date"] + "T" + now_local.strftime("%H:%M:%S")

            yesterday_data = get_costs_fn(**yesterday_params)
            last_week_data = get_costs_fn(**last_week_params)
            
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
        # Použijeme absolutní hodnotu jmenovatele, aby znaménko odpovídalo směru změny i u záporných čísel
        return round(((current - previous) / abs(previous)) * 100, 1)
