import io
import csv
from typing import Any, Dict, List

class DataExportService:
    def __init__(self, billing_service):
        self.billing_service = billing_service

    def generate_monthly_csv(self, cfg: Dict[str, Any], month_str: str, tzinfo) -> str:
        """
        Generuje provozní CSV měsíčního přehledu (den po dni).
        Sloupec Náklady obsahuje pouze variabilní náklady na import; fakturační
        položky a fixní poplatky jsou v samostatných invoice detail exportech.
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
            cost = day.get("cost_total") or 0.0
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

    def generate_invoice_detail_csv(self, cfg: Dict[str, Any], month_str: str, tzinfo, *, kind: str) -> str:
        rows = self.billing_service.get_invoice_detail_rows(cfg, month_str, tzinfo, kind=kind)
        output = io.StringIO()
        writer = csv.writer(output, delimiter=";")

        if kind == "supply":
            writer.writerow(["Datum", "Interval", "EUR/MWh", "CZK/MWh", "Spotřeba kWh", "Kurz", "EUR", "CZK"])
            for row in rows:
                writer.writerow([
                    row["date"], row["interval"], self._csv_number(row["spot_eur_mwh"], 4),
                    self._csv_number(row["spot_czk_mwh"], 4), self._csv_number(row["kwh"], 5),
                    self._csv_number(row["exchange_rate"], 4), self._csv_number(row["result_eur"], 6),
                    self._csv_number(row["result_czk"], 6),
                ])
        else:
            writer.writerow(["Datum", "Interval", "Cena DT OTE EUR/MWh", "Cena DT OTE Kč/MWh", "Cena výkupu EUR/MWh", "Cena výkupu Kč/MWh", "Výkup kWh", "Kurz", "Výsledná cena EUR", "Výsledná cena Kč"])
            for row in rows:
                writer.writerow([
                    row["date"], row["interval"], self._csv_number(row["spot_eur_mwh"], 4),
                    self._csv_number(row["spot_czk_mwh"], 4), self._csv_number(row["effective_eur_mwh"], 4),
                    self._csv_number(row["effective_czk_mwh"], 4), self._csv_number(row["kwh"], 5),
                    self._csv_number(row["exchange_rate"], 4), self._csv_number(row["result_eur"], 6),
                    self._csv_number(row["result_czk"], 6),
                ])
        return output.getvalue()

    @staticmethod
    def _csv_number(value, decimals: int) -> str:
        if value is None:
            return ""
        return f"{float(value):.{decimals}f}".replace(".", ",")
