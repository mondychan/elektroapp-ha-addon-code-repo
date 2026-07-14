from __future__ import annotations

import calendar
import math
from datetime import datetime, timedelta, timezone
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
        compute_fixed_breakdown_for_day: Callable[..., tuple[dict[str, float], dict[str, float]]],
        calculate_sell_coefficient: Callable[..., float] | None = None,
        get_sell_coefficient_kwh: Callable[..., float] | None = None,
        get_influx_cfg: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        get_energy_entities_cfg: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
        parse_influx_interval_to_minutes: Callable[..., int] | None = None,
        query_entity_series: Callable[..., list[dict[str, Any]]] | None = None,
        aggregate_power_points: Callable[..., dict[str, float]] | None = None,
        logger=None,
    ):
        self._get_consumption_points = get_consumption_points
        self._get_export_points = get_export_points
        self._build_price_map_for_date = build_price_map_for_date
        self._get_export_entity_id = get_export_entity_id
        self._get_fee_snapshot_for_date = get_fee_snapshot_for_date
        self._calculate_sell_coefficient = calculate_sell_coefficient or get_sell_coefficient_kwh
        if self._calculate_sell_coefficient is None:
             raise TypeError("BillingService missing calculate_sell_coefficient or get_sell_coefficient_kwh")
        self._compute_fixed_breakdown_for_day = compute_fixed_breakdown_for_day
        self._get_influx_cfg = get_influx_cfg
        self._get_energy_entities_cfg = get_energy_entities_cfg
        self._parse_influx_interval_to_minutes = parse_influx_interval_to_minutes
        self._query_entity_series = query_entity_series
        self._aggregate_power_points = aggregate_power_points
        self._logger = logger

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

    def calculate_daily_invoice(self, cfg: dict[str, Any], date_str: str) -> dict[str, Any]:
        consumption = self._get_consumption_points(cfg, date=date_str)
        tzinfo = consumption["tzinfo"]
        if not consumption.get("has_series", False):
            return {"has_series": False, "kwh_total": None, "variable_cost": None, "items": {}}

        price_map, price_map_utc = self._build_price_map_for_date(cfg, date_str, tzinfo)
        fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
        fees = fee_snapshot.get("kwh_fees", {})
        distribution = fees.get("distribuce", {})
        vt_periods = cfg.get("tarif", {}).get("vt_periods", [])
        dph_multiplier = 1 + (float(fee_snapshot.get("dph_percent") or 0.0) / 100.0)
        items = {
            "spot": 0.0,
            "supplier_service": 0.0,
            "distribution_nt": 0.0,
            "distribution_vt": 0.0,
            "oze": 0.0,
            "electricity_tax": 0.0,
            "system_services": 0.0,
            "nt_kwh": 0.0,
            "vt_kwh": 0.0,
        }
        total_kwh = 0.0
        variable_cost = 0.0

        for entry in consumption["points"]:
            kwh = entry.get("kwh")
            if kwh is None:
                continue
            time_local = datetime.fromisoformat(entry["time"])
            price = price_map.get(time_local.strftime("%Y-%m-%d %H:%M"))
            if price is None:
                time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
                price = price_map_utc.get(time_utc.strftime("%Y-%m-%d %H:%M"))
            if price is None:
                continue
            is_vt = any(start <= time_local.hour < end for start, end in vt_periods)
            tariff = "VT" if is_vt else "NT"
            total_kwh += kwh
            items["spot"] += kwh * price["spot"]
            items["supplier_service"] += kwh * float(fees.get("komodita_sluzba") or 0.0)
            items["oze"] += kwh * float(fees.get("oze") or 0.0)
            items["electricity_tax"] += kwh * float(fees.get("dan") or 0.0)
            items["system_services"] += kwh * float(fees.get("systemove_sluzby") or 0.0)
            items[f"{tariff.lower()}_kwh"] += kwh
            items[f"distribution_{tariff.lower()}"] += kwh * float(distribution.get(tariff) or 0.0)
            variable_cost += kwh * price["final"]

        return {
            "has_series": True,
            "kwh_total": round(total_kwh, 5),
            "variable_cost": round(variable_cost, 5),
            "dph_multiplier": dph_multiplier,
            "items": items,
        }

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
        coef_kwh = self._calculate_sell_coefficient(cfg, fee_snapshot)

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

    def _get_monthly_pv_totals(self, cfg: dict[str, Any], start: datetime, end: datetime, tzinfo) -> dict[str, float]:
        if not (
            self._get_influx_cfg
            and self._get_energy_entities_cfg
            and self._parse_influx_interval_to_minutes
            and self._query_entity_series
            and self._aggregate_power_points
        ):
            return {}

        energy_cfg = self._get_energy_entities_cfg(cfg)
        pv_entity_id = energy_cfg.get("pv_power_total_entity_id")
        if not pv_entity_id:
            return {}

        influx = self._get_influx_cfg(cfg)
        interval = influx.get("interval", "15m")
        interval_minutes = self._parse_influx_interval_to_minutes(interval, default_minutes=15)
        try:
            points = self._query_entity_series(
                influx,
                pv_entity_id,
                start.astimezone(timezone.utc),
                end.astimezone(timezone.utc),
                interval=interval,
                tzinfo=tzinfo,
                numeric=True,
                measurement_candidates=["W", "kW"],
            )
            return self._aggregate_power_points(points, interval_minutes, bucket="day", tzinfo=tzinfo)
        except Exception as exc:
            if self._logger:
                self._logger.warning("Monthly PV production query failed (%s): %s", pv_entity_id, exc)
            return {}

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
        invoice_variable = {
            "spot": 0.0,
            "supplier_service": 0.0,
            "distribution_nt": 0.0,
            "distribution_vt": 0.0,
            "oze": 0.0,
            "electricity_tax": 0.0,
            "system_services": 0.0,
            "nt_kwh": 0.0,
            "vt_kwh": 0.0,
        }
        invoice_fixed = {"standing_charge": 0.0, "breaker": 0.0, "infrastructure": 0.0}

        for day_offset in range(days_in_month):
            date_obj = start_date + timedelta(days=day_offset)
            date_str = date_obj.strftime("%Y-%m-%d")

            fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
            fixed_cfg = fee_snapshot.get("fixed", {})
            daily_cfg = fixed_cfg.get("daily", {})
            monthly_cfg = fixed_cfg.get("monthly", {})
            invoice_fixed["standing_charge"] += float(daily_cfg.get("staly_plat") or 0.0)
            invoice_fixed["breaker"] += float(monthly_cfg.get("jistic") or 0.0) / days_in_month
            invoice_fixed["infrastructure"] += float(monthly_cfg.get("provoz_nesitove_infrastruktury") or 0.0) / days_in_month
            daily_fixed, monthly_fixed = self._compute_fixed_breakdown_for_day(fee_snapshot, days_in_month)
            for key, value in daily_fixed.items():
                fixed_breakdown["daily"][key] = fixed_breakdown["daily"].get(key, 0.0) + value
            for key, value in monthly_fixed.items():
                fixed_breakdown["monthly"][key] = fixed_breakdown["monthly"].get(key, 0.0) + value
            fixed_total += sum(daily_fixed.values()) + sum(monthly_fixed.values())

            if date_obj <= today:
                invoice_day = self.calculate_daily_invoice(cfg, date_str)
                totals = {
                    "kwh_total": invoice_day.get("kwh_total"),
                    "cost_total": invoice_day.get("variable_cost"),
                }
                if totals["kwh_total"] is not None:
                    actual_kwh += totals["kwh_total"]
                    actual_variable += totals["cost_total"]
                    days_with_data += 1
                    for key in invoice_variable:
                        invoice_variable[key] += float(invoice_day.get("items", {}).get(key) or 0.0)
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

        dph_percent = float(cfg.get("dph") or 0.0)
        projection_factor = (days_in_month / days_with_data) if days_with_data else 0.0
        first_day_after_month = start_date + timedelta(days=days_in_month)
        use_billed_quantity_floor = first_day_after_month <= today and days_with_data == days_in_month

        def apply_billed_quantity_floor(variable: dict[str, float]) -> dict[str, float]:
            if not use_billed_quantity_floor:
                return variable
            exact_nt = variable["nt_kwh"]
            exact_vt = variable["vt_kwh"]
            billed_nt = float(math.floor(exact_nt))
            billed_vt = float(math.floor(exact_vt))
            exact_total = exact_nt + exact_vt
            billed_total = billed_nt + billed_vt
            total_ratio = billed_total / exact_total if exact_total > 0 else 0.0
            nt_ratio = billed_nt / exact_nt if exact_nt > 0 else 0.0
            vt_ratio = billed_vt / exact_vt if exact_vt > 0 else 0.0
            adjusted = dict(variable)
            for key in ("spot", "supplier_service", "oze", "electricity_tax", "system_services"):
                adjusted[key] *= total_ratio
            adjusted["distribution_nt"] *= nt_ratio
            adjusted["distribution_vt"] *= vt_ratio
            adjusted["nt_kwh"] = billed_nt
            adjusted["vt_kwh"] = billed_vt
            return adjusted

        def build_invoice(variable_factor: float) -> dict[str, Any]:
            variable = {key: value * variable_factor for key, value in invoice_variable.items()}
            variable = apply_billed_quantity_floor(variable)
            commercial = variable["spot"] + variable["supplier_service"] + invoice_fixed["standing_charge"]
            regulated = (
                variable["distribution_nt"]
                + variable["distribution_vt"]
                + variable["oze"]
                + variable["electricity_tax"]
                + variable["system_services"]
                + invoice_fixed["breaker"]
                + invoice_fixed["infrastructure"]
            )
            supply_without_vat = commercial + regulated
            supply_with_vat = supply_without_vat * (1 + dph_percent / 100.0)
            sell = actual_sell_total * variable_factor if export_days_with_data else 0.0
            return {
                "commercial": {
                    "standing_charge": round(invoice_fixed["standing_charge"], 2),
                    "supplier_service": round(variable["supplier_service"], 2),
                    "spot_energy": round(variable["spot"], 2),
                    "total": round(commercial, 2),
                },
                "regulated": {
                    "distribution_nt_kwh": round(variable["nt_kwh"], 5),
                    "distribution_nt": round(variable["distribution_nt"], 2),
                    "distribution_vt_kwh": round(variable["vt_kwh"], 5),
                    "distribution_vt": round(variable["distribution_vt"], 2),
                    "breaker": round(invoice_fixed["breaker"], 2),
                    "infrastructure": round(invoice_fixed["infrastructure"], 2),
                    "oze": round(variable["oze"], 2),
                    "electricity_tax": round(variable["electricity_tax"], 2),
                    "system_services": round(variable["system_services"], 2),
                    "total": round(regulated, 2),
                },
                "supply_without_vat": round(supply_without_vat, 2),
                "vat": round(supply_with_vat - supply_without_vat, 2),
                "supply_with_vat": round(supply_with_vat, 2),
                "sell_total": round(sell, 2),
                "net_after_sell": round(supply_with_vat - sell, 2),
            }

        result = {
            "month": month_str,
            "days_in_month": days_in_month,
            "days_with_data": days_with_data,
            "actual": actual,
            "projected": projected,
            "fixed_breakdown": fixed_breakdown,
            "invoice": {
                "actual": build_invoice(1.0),
                "projected": build_invoice(projection_factor),
                "dph_percent": dph_percent,
                "price_provider": cfg.get("price_provider"),
                "billed_quantity_rounding": "floor_tariff_kwh" if use_billed_quantity_floor else "exact_interval_kwh",
            },
        }
        monthly_advance = max(float(cfg.get("mesicni_zaloha") or 0.0), 0.0)
        projected_net_total = projected.get("net_total")
        if monthly_advance > 0 and projected_net_total is not None:
            result.update(
                {
                    "monthly_advance": round(monthly_advance, 2),
                    "settlement_estimate": round(monthly_advance - projected_net_total, 2),
                }
            )
        return result

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
        start_local = start.replace(tzinfo=tzinfo)
        next_month_local = next_month.replace(tzinfo=tzinfo)
        pv_totals_by_day = self._get_monthly_pv_totals(cfg, start_local, next_month_local, tzinfo)

        days_in_month = calendar.monthrange(year, month_num)[1]
        days = []
        current = start
        total_kwh = 0.0
        total_cost = 0.0
        total_fixed_cost = 0.0
        total_export_kwh = 0.0
        total_sell = 0.0
        total_pv_kwh = 0.0
        any_pv_series = False
        any_series = False
        any_export_series = False
        while current < next_month and current.date() <= today:
            date_str = current.strftime("%Y-%m-%d")
            totals = self.calculate_daily_totals(cfg, date_str)
            export_totals = self.calculate_daily_export_totals(cfg, date_str)
            pv_kwh = pv_totals_by_day.get(date_str)
            if pv_kwh is not None:
                any_pv_series = True
                total_pv_kwh += pv_kwh
            if totals.get("has_series"):
                any_series = True
            if export_totals.get("has_series"):
                any_export_series = True

            # Denní podíl fixních poplatků (aby měsíční součet = faktuře 1:1)
            fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
            daily_fixed, monthly_fixed = self._compute_fixed_breakdown_for_day(fee_snapshot, days_in_month)
            fixed_cost = sum(daily_fixed.values()) + sum(monthly_fixed.values())
            variable_cost = totals["cost_total"] or 0.0
            day_total_cost = variable_cost + fixed_cost if totals["cost_total"] is not None else None

            days.append(
                {
                    "date": date_str,
                    "kwh_total": totals["kwh_total"],
                    "cost_total": totals["cost_total"],          # variable only (kWh * final_price)
                    "fixed_cost_total": round(fixed_cost, 2),    # daily share of fixed charges
                    "total_cost": round(day_total_cost, 2) if day_total_cost is not None else None,  # variable + fixed
                    "pv_kwh": pv_kwh,
                    "export_kwh_total": export_totals["export_kwh_total"],
                    "sell_total": export_totals["sell_total"],
                }
            )
            if totals["kwh_total"] is not None:
                total_kwh += totals["kwh_total"]
            if totals["cost_total"] is not None:
                total_cost += totals["cost_total"]
            total_fixed_cost += fixed_cost  # always — fixed charges apply even on zero-consumption days
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

        summary = {
            "kwh_total": round(total_kwh, 5),
            "cost_total": round(total_cost, 5),                     # variable only (kWh × final_price)
            "fixed_cost_total": round(total_fixed_cost, 2),          # daily share of fixed charges → matches invoice
            "total_cost": round(total_cost + total_fixed_cost, 2),   # variable + fixed = invoice amount
            "pv_kwh": round(total_pv_kwh, 5) if any_pv_series else None,
            "export_kwh_total": round(total_export_kwh, 5) if any_export_series else None,
            "sell_total": round(total_sell, 5) if any_export_series else None,
        }
        monthly_advance = max(float(cfg.get("mesicni_zaloha") or 0.0), 0.0)
        if monthly_advance > 0:
            billing = self.compute_monthly_billing(cfg, month, tzinfo, require_data=False)
            projected_net_total = billing.get("projected", {}).get("net_total")
            if projected_net_total is not None:
                summary.update(
                    {
                        "monthly_advance": round(monthly_advance, 2),
                        "projected_net_total": round(projected_net_total, 2),
                        # Positive means refund, negative means surcharge.
                        "settlement_estimate": round(monthly_advance - projected_net_total, 2),
                    }
                )

        return {
            "month": month,
            "days": days,
            "summary": summary,
        }

    def get_invoice_detail_rows(self, cfg: dict[str, Any], month_str: str, tzinfo, *, kind: str) -> list[dict[str, Any]]:
        if kind not in {"supply", "export"}:
            raise ValueError("Invoice detail kind must be 'supply' or 'export'.")
        if not re.match(r"^\d{4}-\d{2}$", month_str):
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
        year, month_num = map(int, month_str.split("-"))
        days_in_month = calendar.monthrange(year, month_num)[1]
        today = datetime.now(tzinfo).date()
        rows: list[dict[str, Any]] = []

        for day_num in range(1, days_in_month + 1):
            date_obj = datetime(year, month_num, day_num).date()
            if date_obj > today:
                break
            date_str = date_obj.isoformat()
            series = self._get_consumption_points(cfg, date=date_str) if kind == "supply" else self._get_export_points(cfg, date=date_str)
            price_map, price_map_utc = self._build_price_map_for_date(cfg, date_str, tzinfo)
            fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_str, tzinfo)
            coefficient_mwh = self._calculate_sell_coefficient(cfg, fee_snapshot) * 1000.0
            for entry in series.get("points", []):
                kwh = entry.get("kwh")
                if kwh is None:
                    continue
                time_local = datetime.fromisoformat(entry["time"])
                price = price_map.get(time_local.strftime("%Y-%m-%d %H:%M"))
                if price is None:
                    time_utc = datetime.fromisoformat(entry["time_utc"].replace("Z", "+00:00"))
                    price = price_map_utc.get(time_utc.strftime("%Y-%m-%d %H:%M"))
                if price is None:
                    continue
                start_minutes = time_local.hour * 60 + time_local.minute
                end_minutes = start_minutes + 14
                interval = f"{start_minutes // 60:02d}:{start_minutes % 60:02d} - {end_minutes // 60:02d}:{end_minutes % 60:02d}"
                spot_czk_mwh = float(price.get("price_czk_mwh") or price["spot"] * 1000.0)
                spot_eur_mwh = price.get("price_eur_mwh")
                exchange_rate = price.get("eur_czk_rate")
                effective_czk_mwh = spot_czk_mwh if kind == "supply" else spot_czk_mwh - coefficient_mwh
                effective_eur_mwh = None
                if spot_eur_mwh is not None:
                    effective_eur_mwh = float(spot_eur_mwh)
                    if kind == "export" and exchange_rate:
                        effective_eur_mwh -= coefficient_mwh / float(exchange_rate)
                rows.append(
                    {
                        "date": date_str,
                        "interval": interval,
                        "spot_eur_mwh": spot_eur_mwh,
                        "spot_czk_mwh": spot_czk_mwh,
                        "effective_eur_mwh": effective_eur_mwh,
                        "effective_czk_mwh": effective_czk_mwh,
                        "kwh": float(kwh),
                        "exchange_rate": exchange_rate,
                        "result_eur": None if effective_eur_mwh is None else float(kwh) * effective_eur_mwh / 1000.0,
                        "result_czk": float(kwh) * effective_czk_mwh / 1000.0,
                    }
                )
        return rows

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
