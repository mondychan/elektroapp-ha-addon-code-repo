import io
import csv
from typing import Any, Dict, List

class DataExportService:
    def __init__(self, billing_service):
        self.billing_service = billing_service

    def generate_monthly_csv(self, cfg: Dict[str, Any], month_str: str, tzinfo) -> str:
        """
        Generuje CSV pro měsíční přehled (den po dni).
        
        Sloupec Naklady (Kc) nyní odpovídá faktuře 1:1 — zahrnuje variabilní
        i fixní poplatky (jistič, stálý plat, provoz infrastruktury) rozpočítané
        na den. V prvním řádku za daty je uveden součet.
        """
        data = self.billing_service.get_daily_summary(month=month_str, cfg=cfg, tzinfo=tzinfo)
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        
        # Hlavička CSV
        writer.writerow([
            "Datum", 
            "Nakup (kWh)", 
            "Vyrobeno FV (kWh)",
            "Naklady (Kc)", 
            "Prodej (kWh)", 
            "Trzby (Kc)", 
            "Netto (kWh)", 
            "Netto (Kc)"
        ])
        
        days = data.get("days", [])
        total_kwh = 0.0
        total_cost = 0.0
        total_export = 0.0
        total_sell = 0.0
        
        for day in days:
            kwh = day.get("kwh_total") or 0.0
            pv_kwh = day.get("pv_kwh")
            # total_cost zahrnuje variabilní + fixní (od 0.3.51).
            # Pro zpětnou kompatibilitu fallback na cost_total (variable only).
            cost = day.get("total_cost") or day.get("cost_total") or 0.0
            export = day.get("export_kwh_total") or 0.0
            sell = day.get("sell_total") or 0.0
            
            net_kwh = kwh - export
            net_cost = cost - sell
            
            writer.writerow([
                day.get("date"),
                f"{kwh:.3f}".replace('.', ','),
                "" if pv_kwh is None else f"{float(pv_kwh):.3f}".replace('.', ','),
                f"{cost:.2f}".replace('.', ','),
                f"{export:.3f}".replace('.', ','),
                f"{sell:.2f}".replace('.', ','),
                f"{net_kwh:.3f}".replace('.', ','),
                f"{net_cost:.2f}".replace('.', ',')
            ])
            total_kwh += kwh
            total_cost += cost
            total_export += export
            total_sell += sell
        
        # Součtový řádek
        total_net_kwh = total_kwh - total_export
        total_net_cost = total_cost - total_sell
        writer.writerow([
            "CELKEM",
            f"{total_kwh:.3f}".replace('.', ','),
            "",
            f"{total_cost:.2f}".replace('.', ','),
            f"{total_export:.3f}".replace('.', ','),
            f"{total_sell:.2f}".replace('.', ','),
            f"{total_net_kwh:.3f}".replace('.', ','),
            f"{total_net_cost:.2f}".replace('.', ','),
        ])
            
        return output.getvalue()
