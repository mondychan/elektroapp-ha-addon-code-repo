from __future__ import annotations

import calendar
from datetime import datetime, timedelta
import re
from typing import Any, Callable

from fastapi import HTTPException


class BillingService:
    def __init__(
        self,
        *,
        get_consumption_points: Callable[..., dict[str, Any]],
        get_export_points: Callable[..., dict[str, Any]],
        build_price_map_for_date: Callable[..., tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]],
        get_export_entity_id: Callable[[dict[str, Any]], str | None],
        get_fee_snapshot_for_date: Callable[..., dict[str, Any]],
        get_sell_coefficient_kwh: Callable[..., float],
        compute_fixed_breakdown_for_day: Callable[..., tuple[dict[str, float], dict[str, float]]],
    ):
        self._get_consumption_points = get_consumption_points
        self._get_export_points = get_export_points
        self._build_price_map_for_date = build_price_map_for_date
        self._get_export_entity_id = get_export_entity_id
        self._get_fee_snapshot_for_date = get_fee_snapshot_for_date
        self._get_sell_coefficient_kwh = get_sell_coefficient_kwh
        self._compute_fixed_breakdown_for_day = compute_fixed_breakdown_for_day

    def calculate_daily_totals(self, cfg: dict[str, Any], date_str: str) -> dict[str, Any]:
        consumption = self._get_consumption_points(cfg, date=date_str)
        tzinfo = consumption["tzinfo"]
        has_series = consumption.get("has_series", False)
        if not has_series:
            return {"kwh_total": None, "cost_total": None, "has_series": has_series}
        price_map, price_map_utc = self._build_price_map_for_date(cfg, date_str, tzinfo)

        total_kwh = 0.0
        total_cost = 0.0
        count = 0
        for entry in consumption["points"]:
            kwh = entry["kwh"]
            time_local = datetime.fromisoformat(entry["time"])
            key = time_local.strftime("%Y-%m-%d %H:%M")
            price = price_map.get(key)
            if price is None:
                time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
                key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
                price = price_map_utc.get(key_utc)
            final_price = price["final"] if price else None
            if kwh is not None and final_price is not None:
                total_kwh += kwh
                total_cost += kwh * final_price
                count += 1

        if count == 0:
            return {"kwh_total": None, "cost_total": None, "has_series": has_series}
        return {"kwh_total": round(total_kwh, 5), "cost_total": round(total_cost, 5), "has_series": has_series}

    def calculate_daily_export_totals(self, cfg: dict[str, Any], date_str: str) -> dict[str, Any]:
        export_entity_id = self._get_export_entity_id(cfg)
        if not export_entity_id:
            return {"export_kwh_total": None, "sell_total": None, "has_series": False}
        export = self._get_export_points(cfg, date=date_str)
        tzinfo = export["tzinfo"]
        has_series = export.get("has_series", False)
        if not has_series:
            return {"export_kwh_total": None, "sell_total": None, "has_series": has_series}
        price_map, price_map_utc = self._build_price_map_for_date(cfg, date_str, tzinfo)
        fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
        coef_kwh = self._get_sell_coefficient_kwh(cfg, fee_snapshot)

        total_kwh = 0.0
        total_sell = 0.0
        count = 0
        for entry in export["points"]:
            kwh = entry["kwh"]
            time_local = datetime.fromisoformat(entry["time"])
            key = time_local.strftime("%Y-%m-%d %H:%M")
            price = price_map.get(key)
            if price is None:
                time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
                key_utc = time_utc.strftime("%Y-%m-%d %H:%M")
                price = price_map_utc.get(key_utc)
            spot_price = price["spot"] if price else None
            sell_price = spot_price - coef_kwh if spot_price is not None else None
            if kwh is not None and sell_price is not None:
                total_kwh += kwh
                total_sell += kwh * sell_price
                count += 1

        if count == 0:
            return {"export_kwh_total": None, "sell_total": None, "has_series": has_series}
        return {
            "export_kwh_total": round(total_kwh, 5),
            "sell_total": round(total_sell, 5),
            "has_series": has_series,
        }

    def compute_monthly_billing(
        self,
        cfg: dict[str, Any],
        month_str: str,
        tzinfo,
        require_data: bool | None = None,
    ) -> dict[str, Any]:
        if not re.match(r"^\d{4}-\d{2}$", month_str):
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
        year, month_num = map(int, month_str.split("-"))
        days_in_month = calendar.monthrange(year, month_num)[1]
        start_date = datetime(year, month_num, 1).date()
        today = datetime.now(tzinfo).date()
        if require_data is None:
            require_data = start_date.year == today.year and start_date.month == today.month

        actual_variable = 0.0
        actual_kwh = 0.0
        actual_export_kwh = 0.0
        actual_sell_total = 0.0
        days_with_data = 0
        export_days_with_data = 0
        fixed_total = 0.0
        fixed_breakdown = {"daily": {}, "monthly": {}}

        for day_offset in range(days_in_month):
            date_obj = start_date + timedelta(days=day_offset)
            date_str = date_obj.strftime("%Y-%m-%d")

            fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
            daily_fixed, monthly_fixed = self._compute_fixed_breakdown_for_day(fee_snapshot, days_in_month)
            for key, value in daily_fixed.items():
                fixed_breakdown["daily"][key] = fixed_breakdown["daily"].get(key, 0.0) + value
            for key, value in monthly_fixed.items():
                fixed_breakdown["monthly"][key] = fixed_breakdown["monthly"].get(key, 0.0) + value
            fixed_total += sum(daily_fixed.values()) + sum(monthly_fixed.values())

            if date_obj <= today:
                totals = self.calculate_daily_totals(cfg, date_str)
                if totals["kwh_total"] is not None:
                    actual_kwh += totals["kwh_total"]
                    actual_variable += totals["cost_total"]
                    days_with_data += 1
                export_totals = self.calculate_daily_export_totals(cfg, date_str)
                if export_totals["export_kwh_total"] is not None:
                    actual_export_kwh += export_totals["export_kwh_total"]
                if export_totals["sell_total"] is not None:
                    actual_sell_total += export_totals["sell_total"]
                    export_days_with_data += 1

        if days_with_data == 0 and start_date <= today and require_data:
            raise HTTPException(
                status_code=500,
                detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
            )

        if days_with_data == 0:
            actual = {
                "kwh_total": None,
                "variable_cost": None,
                "fixed_cost": None,
                "total_cost": None,
                "export_kwh_total": None,
                "sell_total": None,
                "net_total": None,
            }
            projected = {
                "variable_cost": None,
                "fixed_cost": None,
                "total_cost": None,
                "sell_total": None,
                "net_total": None,
            }
        else:
            projected_variable = (actual_variable / days_with_data) * days_in_month
            projected_sell_total = None
            if export_days_with_data > 0:
                projected_sell_total = (actual_sell_total / export_days_with_data) * days_in_month
            actual_sell_value = round(actual_sell_total, 5) if export_days_with_data > 0 else None
            actual_export_value = round(actual_export_kwh, 5) if export_days_with_data > 0 else None
            projected_sell_value = round(projected_sell_total, 5) if projected_sell_total is not None else None
            actual_total_cost = actual_variable + fixed_total
            projected_total_cost = projected_variable + fixed_total
            actual_net_total = actual_total_cost - (actual_sell_value or 0.0)
            projected_net_total = projected_total_cost - (projected_sell_value or 0.0)
            actual = {
                "kwh_total": round(actual_kwh, 5),
                "variable_cost": round(actual_variable, 5),
                "fixed_cost": round(fixed_total, 5),
                "total_cost": round(actual_total_cost, 5),
                "export_kwh_total": actual_export_value,
                "sell_total": actual_sell_value,
                "net_total": round(actual_net_total, 5),
            }
            projected = {
                "variable_cost": round(projected_variable, 5),
                "fixed_cost": round(fixed_total, 5),
                "total_cost": round(projected_total_cost, 5),
                "sell_total": projected_sell_value,
                "net_total": round(projected_net_total, 5),
            }
        fixed_breakdown["daily"] = {k: round(v, 5) for k, v in fixed_breakdown["daily"].items()}
        fixed_breakdown["monthly"] = {k: round(v, 5) for k, v in fixed_breakdown["monthly"].items()}

        return {
            "month": month_str,
            "days_in_month": days_in_month,
            "days_with_data": days_with_data,
            "actual": actual,
            "projected": projected,
            "fixed_breakdown": fixed_breakdown,
        }

    def get_daily_summary(self, *, month: str, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        if not re.match(r"^\d{4}-\d{2}$", month):
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
        year, month_num = map(int, month.split("-"))
        start = datetime(year, month_num, 1)
        if month_num == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month_num + 1, 1)
        today = datetime.now(tzinfo).date()

        days = []
        current = start
        total_kwh = 0.0
        total_cost = 0.0
        total_export_kwh = 0.0
        total_sell = 0.0
        any_series = False
        any_export_series = False
        while current < next_month and current.date() <= today:
            date_str = current.strftime("%Y-%m-%d")
            totals = self.calculate_daily_totals(cfg, date_str)
            export_totals = self.calculate_daily_export_totals(cfg, date_str)
            if totals.get("has_series"):
                any_series = True
            if export_totals.get("has_series"):
                any_export_series = True
            days.append(
                {
                    "date": date_str,
                    "kwh_total": totals["kwh_total"],
                    "cost_total": totals["cost_total"],
                    "export_kwh_total": export_totals["export_kwh_total"],
                    "sell_total": export_totals["sell_total"],
                }
            )
            if totals["kwh_total"] is not None:
                total_kwh += totals["kwh_total"]
            if totals["cost_total"] is not None:
                total_cost += totals["cost_total"]
            if export_totals["export_kwh_total"] is not None:
                total_export_kwh += export_totals["export_kwh_total"]
            if export_totals["sell_total"] is not None:
                total_sell += export_totals["sell_total"]
            current += timedelta(days=1)

        if not any_series and start.date() <= today:
            raise HTTPException(
                status_code=500,
                detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
            )

        return {
            "month": month,
            "days": days,
            "summary": {
                "kwh_total": round(total_kwh, 5),
                "cost_total": round(total_cost, 5),
                "export_kwh_total": round(total_export_kwh, 5) if any_export_series else None,
                "sell_total": round(total_sell, 5) if any_export_series else None,
            },
        }

    def get_billing_month(self, *, month: str, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        return self.compute_monthly_billing(cfg, month, tzinfo)

    def get_billing_year(self, *, year: int, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        now = datetime.now(tzinfo)
        current_year = now.year
        current_month = now.month
        if year > current_year:
            return {"year": year, "months": [], "totals": {"actual": {}, "projected": {}}}

        end_month = 12 if year < current_year else current_month
        months = []
        totals_actual_var = 0.0
        totals_actual_fixed = 0.0
        totals_actual_total = 0.0
        totals_actual_net = 0.0
        totals_projected_var = 0.0
        totals_projected_fixed = 0.0
        totals_projected_total = 0.0
        totals_projected_net = 0.0

        for month_num in range(1, end_month + 1):
            month_str = f"{year}-{month_num:02d}"
            data = self.compute_monthly_billing(cfg, month_str, tzinfo, require_data=False)
            months.append(
                {
                    "month": data["month"],
                    "days_in_month": data["days_in_month"],
                    "days_with_data": data["days_with_data"],
                    "actual": data["actual"],
                    "projected": data["projected"],
                }
            )
            if data["days_with_data"] > 0:
                totals_actual_var += data["actual"]["variable_cost"]
                totals_actual_fixed += data["actual"]["fixed_cost"]
                totals_actual_total += data["actual"]["total_cost"]
                if data["actual"].get("net_total") is not None:
                    totals_actual_net += data["actual"]["net_total"]
                totals_projected_var += data["projected"]["variable_cost"]
                totals_projected_fixed += data["projected"]["fixed_cost"]
                totals_projected_total += data["projected"]["total_cost"]
                if data["projected"].get("net_total") is not None:
                    totals_projected_net += data["projected"]["net_total"]

        totals = {
            "actual": {
                "variable_cost": round(totals_actual_var, 5),
                "fixed_cost": round(totals_actual_fixed, 5),
                "total_cost": round(totals_actual_total, 5),
                "net_total": round(totals_actual_net, 5),
            },
            "projected": {
                "variable_cost": round(totals_projected_var, 5),
                "fixed_cost": round(totals_projected_fixed, 5),
                "total_cost": round(totals_projected_total, 5),
                "net_total": round(totals_projected_net, 5),
            },
        }
        return {"year": year, "months": months, "totals": totals}
