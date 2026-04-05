import io
import csv
from typing import Any, Dict, List

class DataExportService:
    def __init__(self, billing_service):
        self.billing_service = billing_service

    def generate_monthly_csv(self, cfg: Dict[str, Any], month_str: str, tzinfo) -> str:
        """
        Generuje CSV pro měsíční přehled (den po dni).
        """
        data = self.billing_service.get_daily_summary(month=month_str, cfg=cfg, tzinfo=tzinfo)
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Hlavička CSV
        writer.writerow([
            "Datum", 
            "Nakup (kWh)", 
            "Naklady (Kc)", 
            "Prodej (kWh)", 
            "Trzby (Kc)", 
            "Netto (kWh)", 
            "Netto (Kc)"
        ])
        
        days = data.get("days", [])
        for day in days:
            kwh = day.get("kwh_total") or 0.0
            cost = day.get("cost_total") or 0.0
            export = day.get("export_kwh_total") or 0.0
            sell = day.get("sell_total") or 0.0
            
            net_kwh = kwh - export
            net_cost = cost - sell
            
            writer.writerow([
                day.get("date"),
                f"{kwh:.3f}".replace('.', ','),
                f"{cost:.2f}".replace('.', ','),
                f"{export:.3f}".replace('.', ','),
                f"{sell:.2f}".replace('.', ','),
                f"{net_kwh:.3f}".replace('.', ','),
                f"{net_cost:.2f}".replace('.', ',')
            ])
            
        return output.getvalue()
