from __future__ import annotations

import calendar
from datetime import datetime
from typing import Any, Callable

from fastapi import HTTPException
from requests import RequestException


class InsightsService:
    def __init__(
        self,
        *,
        get_influx_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        get_energy_entities_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        build_energy_balance_range: Callable[..., dict[str, Any]],
        parse_influx_interval_to_minutes: Callable[..., int],
        query_entity_series: Callable[..., list[dict[str, Any]]],
        aggregate_power_points: Callable[..., dict[str, float]],
        build_energy_balance_buckets: Callable[..., list[dict[str, Any]]],
        get_prices_for_date: Callable[..., list[dict[str, Any]]],
        aggregate_hourly_from_price_entries: Callable[..., list[float | None]],
        get_consumption_points: Callable[..., dict[str, Any]],
        get_export_points: Callable[..., dict[str, Any]],
        aggregate_hourly_from_kwh_points: Callable[..., list[float | None]],
        logger,
    ):
        self._get_influx_cfg = get_influx_cfg
        self._get_energy_entities_cfg = get_energy_entities_cfg
        self._build_energy_balance_range = build_energy_balance_range
        self._parse_influx_interval_to_minutes = parse_influx_interval_to_minutes
        self._query_entity_series = query_entity_series
        self._aggregate_power_points = aggregate_power_points
        self._build_energy_balance_buckets = build_energy_balance_buckets
        self._get_prices_for_date = get_prices_for_date
        self._aggregate_hourly_from_price_entries = aggregate_hourly_from_price_entries
        self._get_consumption_points = get_consumption_points
        self._get_export_points = get_export_points
        self._aggregate_hourly_from_kwh_points = aggregate_hourly_from_kwh_points
        self._logger = logger

    def get_energy_balance(self, *, period: str, anchor: str | None, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        influx = self._get_influx_cfg(cfg)
        tzinfo = tzinfo or datetime.now().astimezone().tzinfo
        energy_cfg = self._get_energy_entities_cfg(cfg)
        range_info = self._build_energy_balance_range(period, anchor, tzinfo)
        interval = influx.get("interval", "15m")
        interval_minutes = self._parse_influx_interval_to_minutes(interval, default_minutes=15)
        power_measurements = ["W", "kW"]

        entity_map = {
            "pv_kwh": energy_cfg.get("pv_power_total_entity_id"),
            "house_load_kwh": energy_cfg.get("house_load_power_entity_id"),
            "grid_import_kwh": energy_cfg.get("grid_import_power_entity_id"),
            "grid_export_kwh": energy_cfg.get("grid_export_power_entity_id"),
        }

        aggregated = {}
        for key, entity_id in entity_map.items():
            if not entity_id:
                aggregated[key] = {}
                continue
            points = self._query_entity_series(
                influx,
                entity_id,
                range_info["start_utc"],
                range_info["end_utc"],
                interval=interval,
                tzinfo=tzinfo,
                numeric=True,
                measurement_candidates=power_measurements,
            )
            aggregated[key] = self._aggregate_power_points(
                points,
                interval_minutes,
                bucket=range_info["bucket"],
                tzinfo=tzinfo,
            )

        buckets = self._build_energy_balance_buckets(range_info, tzinfo)
        rows = []
        totals = {
            "pv_kwh": 0.0,
            "house_load_kwh": 0.0,
            "grid_import_kwh": 0.0,
            "grid_export_kwh": 0.0,
        }
        for bucket in buckets:
            row = {
                "key": bucket["key"],
                "label": bucket["label"],
                "start": bucket["start"],
            }
            for metric_key in totals.keys():
                value = aggregated.get(metric_key, {}).get(bucket["key"])
                row[metric_key] = value if value is not None else 0.0
                totals[metric_key] += row[metric_key]
            rows.append(row)

        return {
            "period": range_info["period"],
            "anchor": range_info["anchor"],
            "bucket": range_info["bucket"],
            "range": {
                "start": range_info["start_local"].isoformat(),
                "end": range_info["end_local"].isoformat(),
            },
            "interval": interval,
            "entities": entity_map,
            "points": rows,
            "totals": {k: round(v, 5) for k, v in totals.items()},
        }

    def get_history_heatmap(
        self,
        *,
        month: str,
        metric: str,
        cfg: dict[str, Any],
        tzinfo,
    ) -> dict[str, Any]:
        if not month or not isinstance(month, str) or not month[:4].isdigit():
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
        if len(month) != 7 or month[4] != "-" or not month[5:].isdigit():
            raise HTTPException(status_code=400, detail="Invalid month format. Use YYYY-MM.")
        metric_norm = (metric or "buy").strip().lower()
        if metric_norm not in {"price", "buy", "export"}:
            raise HTTPException(status_code=400, detail="Invalid metric. Use price|buy|export.")

        year, month_num = map(int, month.split("-"))
        days_in_month = calendar.monthrange(year, month_num)[1]
        today_local = datetime.now(tzinfo).date()
        month_rows = []
        min_value = None
        max_value = None

        for day in range(1, days_in_month + 1):
            date_obj = datetime(year, month_num, day).date()
            date_str = date_obj.strftime("%Y-%m-%d")
            if date_obj > today_local:
                values = [None] * 24
            else:
                try:
                    if metric_norm == "price":
                        entries = self._get_prices_for_date(cfg, date_str, tzinfo)
                        values = self._aggregate_hourly_from_price_entries(entries)
                    elif metric_norm == "buy":
                        consumption = self._get_consumption_points(cfg, date=date_str)
                        values = self._aggregate_hourly_from_kwh_points(consumption.get("points", []))
                    else:
                        export = self._get_export_points(cfg, date=date_str)
                        values = self._aggregate_hourly_from_kwh_points(export.get("points", []))
                except (HTTPException, RequestException, ValueError, TypeError) as exc:
                    self._logger.warning("Heatmap load failed (%s %s): %s", metric_norm, date_str, exc)
                    values = [None] * 24

            for val in values:
                if val is None:
                    continue
                min_value = val if min_value is None else min(min_value, val)
                max_value = val if max_value is None else max(max_value, val)

            month_rows.append(
                {
                    "date": date_str,
                    "day": day,
                    "weekday": date_obj.weekday(),
                    "values": values,
                }
            )

        return {
            "month": month,
            "metric": metric_norm,
            "hours": list(range(24)),
            "days": month_rows,
            "stats": {
                "min": round(min_value, 5) if min_value is not None else None,
                "max": round(max_value, 5) if max_value is not None else None,
            },
        }
