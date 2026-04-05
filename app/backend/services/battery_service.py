from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from fastapi import HTTPException
from requests import RequestException


class BatteryService:
    def __init__(
        self,
        *,
        get_influx_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        get_local_tz: Callable[[str | None], Any],
        get_battery_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        get_energy_entities_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        get_forecast_solar_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        parse_time_range: Callable[..., tuple[Any, Any]],
        has_battery_required_cfg: Callable[[dict[str, Any]], bool],
        query_entity_series: Callable[..., list[dict[str, Any]]],
        build_battery_history_points: Callable[..., list[dict[str, Any]]],
        get_last_non_null_value: Callable[..., dict[str, Any] | None],
        average_recent_power: Callable[..., float | None],
        safe_query_entity_last_value: Callable[..., dict[str, Any] | None],
        parse_influx_interval_to_minutes: Callable[..., int],
        query_recent_slot_profile_by_day_type: Callable[..., dict[str, float]],
        build_hybrid_battery_projection: Callable[..., dict[str, Any] | None],
        build_battery_projection: Callable[..., dict[str, Any] | None],
        iso_to_display_hhmm: Callable[[Any], str | None],
        logger,
    ):
        self._get_influx_cfg = get_influx_cfg
        self._get_local_tz = get_local_tz
        self._get_battery_cfg = get_battery_cfg
        self._get_energy_entities_cfg = get_energy_entities_cfg
        self._get_forecast_solar_cfg = get_forecast_solar_cfg
        self._parse_time_range = parse_time_range
        self._has_battery_required_cfg = has_battery_required_cfg
        self._query_entity_series = query_entity_series
        self._build_battery_history_points = build_battery_history_points
        self._get_last_non_null_value = get_last_non_null_value
        self._average_recent_power = average_recent_power
        self._safe_query_entity_last_value = safe_query_entity_last_value
        self._parse_influx_interval_to_minutes = parse_influx_interval_to_minutes
        self._query_recent_slot_profile_by_day_type = query_recent_slot_profile_by_day_type
        self._build_hybrid_battery_projection = build_hybrid_battery_projection
        self._build_battery_projection = build_battery_projection
        self._iso_to_display_hhmm = iso_to_display_hhmm
        self._logger = logger

    def get_battery(self, *, date: str | None, cfg: dict[str, Any], tzinfo=None) -> dict[str, Any]:
        influx = self._get_influx_cfg(cfg)
        tzinfo = tzinfo or self._get_local_tz(influx.get("timezone"))
        battery_cfg = self._get_battery_cfg(cfg)
        energy_cfg = self._get_energy_entities_cfg(cfg)
        forecast_cfg = self._get_forecast_solar_cfg(cfg)

        selected_date = date or datetime.now(tzinfo).strftime("%Y-%m-%d")
        start_utc, end_utc = self._parse_time_range(selected_date, None, None, tzinfo)
        is_today = selected_date == datetime.now(tzinfo).strftime("%Y-%m-%d")

        if not battery_cfg.get("enabled"):
            return {
                "enabled": False,
                "configured": False,
                "date": selected_date,
                "detail": "Battery feature is disabled in config.",
            }
        if not self._has_battery_required_cfg(battery_cfg):
            return {
                "enabled": True,
                "configured": False,
                "date": selected_date,
                "detail": "Missing battery config (soc_entity_id, power_entity_id, usable_capacity_kwh).",
            }

        history_interval = influx.get("interval", "15m")
        kwh_measurements = ["kWh", "Wh"]
        power_measurements = ["W", "kW"]
        soc_measurements = ["%", "percent"]
        state_measurements = ["state"]
        soc_series = self._query_entity_series(
            influx,
            battery_cfg["soc_entity_id"],
            start_utc,
            end_utc,
            interval=history_interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=soc_measurements,
        )
        power_series = self._query_entity_series(
            influx,
            battery_cfg["power_entity_id"],
            start_utc,
            end_utc,
            interval=history_interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=power_measurements,
        )

        def _normalize_points_to_w(ps):
            for p in ps:
                if p.get("value") is not None and str(p.get("unit") or "").lower() == "kw":
                    p["value"] = float(p["value"]) * 1000.0
            return ps

        power_series = _normalize_points_to_w(power_series)
        history_points = self._build_battery_history_points(soc_series, power_series)
        last_soc_point = self._get_last_non_null_value(soc_series)
        last_power_point = self._get_last_non_null_value(power_series)

        now_local = datetime.now(tzinfo)
        avg_power_w = None
        if is_today:
            smoothing_start_utc = (now_local - timedelta(minutes=battery_cfg["eta_smoothing_minutes"])).astimezone(
                timezone.utc
            )
            smoothing_end_utc = now_local.astimezone(timezone.utc) + timedelta(minutes=1)
            trend_series = self._query_entity_series(
                influx,
                battery_cfg["power_entity_id"],
                smoothing_start_utc,
                smoothing_end_utc,
                interval="1m",
                tzinfo=tzinfo,
                numeric=True,
                measurement_candidates=power_measurements,
            )
            trend_series = _normalize_points_to_w(trend_series)
            avg_power_w = self._average_recent_power(trend_series)

        latest_soc = self._safe_query_entity_last_value(
            influx,
            battery_cfg["soc_entity_id"],
            tzinfo=tzinfo,
            numeric=True,
            label="soc",
            measurement_candidates=soc_measurements,
        )
        latest_power = self._safe_query_entity_last_value(
            influx,
            battery_cfg["power_entity_id"],
            tzinfo=tzinfo,
            numeric=True,
            label="battery_power",
            measurement_candidates=power_measurements,
        )
        if (latest_soc is None or latest_soc.get("value") is None) and last_soc_point:
            latest_soc = {
                "time": last_soc_point["time"],
                "time_utc": last_soc_point["time_utc"],
                "value": last_soc_point["value"],
            }
        if (latest_power is None or latest_power.get("value") is None) and last_power_point:
            latest_power = {
                "time": last_power_point["time"],
                "time_utc": last_power_point["time_utc"],
                "value": last_power_point["value"],
            }

        soc_percent = latest_soc.get("value") if latest_soc else None
        battery_power_w = latest_power.get("value") if latest_power else None
        usable_capacity_kwh = max(0.0, battery_cfg["usable_capacity_kwh"])
        reserve_soc_percent = max(0.0, min(100.0, battery_cfg["reserve_soc_percent"]))
        clamped_soc = None if soc_percent is None else max(0.0, min(100.0, soc_percent))
        stored_kwh = round(usable_capacity_kwh * clamped_soc / 100.0, 4) if clamped_soc is not None else None
        available_to_reserve_kwh = (
            round(usable_capacity_kwh * max(0.0, clamped_soc - reserve_soc_percent) / 100.0, 4)
            if clamped_soc is not None
            else None
        )
        remaining_to_full_kwh = (
            round(usable_capacity_kwh * max(0.0, 100.0 - clamped_soc) / 100.0, 4) if clamped_soc is not None else None
        )

        threshold = battery_cfg["min_power_threshold_w"]
        if battery_power_w is None:
            battery_state = "unknown"
        elif battery_power_w > threshold:
            battery_state = "charging"
        elif battery_power_w < -threshold:
            battery_state = "discharging"
        else:
            battery_state = "idle"

        def _latest_numeric(entity_id, label, measurements=None):
            record = self._safe_query_entity_last_value(
                influx,
                entity_id,
                tzinfo=tzinfo,
                numeric=True,
                label=label,
                measurement_candidates=measurements,
            )
            if not record or record.get("value") is None:
                return None
            val = float(record["value"])
            if str(record.get("unit") or "").lower() == "kw":
                return val * 1000.0
            return val

        def _latest_raw(entity_id, label, measurements=None):
            record = self._safe_query_entity_last_value(
                influx,
                entity_id,
                tzinfo=tzinfo,
                numeric=False,
                label=label,
                measurement_candidates=measurements,
            )
            return None if not record else record.get("raw_value")

        current_energy = {
            "house_load_w": _latest_numeric(energy_cfg.get("house_load_power_entity_id"), "house_load", power_measurements),
            "grid_import_w": _latest_numeric(
                energy_cfg.get("grid_import_power_entity_id"), "grid_import", power_measurements
            ),
            "grid_export_w": _latest_numeric(
                energy_cfg.get("grid_export_power_entity_id"), "grid_export", power_measurements
            ),
            "pv_power_total_w": _latest_numeric(energy_cfg.get("pv_power_total_entity_id"), "pv_total", power_measurements),
            "pv_power_1_w": _latest_numeric(energy_cfg.get("pv_power_1_entity_id"), "pv_1", power_measurements),
            "pv_power_2_w": _latest_numeric(energy_cfg.get("pv_power_2_entity_id"), "pv_2", power_measurements),
            "battery_input_today_kwh": _latest_numeric(
                battery_cfg.get("input_energy_today_entity_id"),
                "battery_input_today",
                kwh_measurements,
            ),
            "battery_output_today_kwh": _latest_numeric(
                battery_cfg.get("output_energy_today_entity_id"),
                "battery_output_today",
                kwh_measurements,
            ),
        }

        forecast_payload = {"enabled": bool(forecast_cfg.get("enabled")), "available": False}
        if forecast_cfg.get("enabled"):
            forecast_payload.update(
                {
                    "power_now_w": _latest_numeric(
                        forecast_cfg.get("power_now_entity_id"), "forecast_power_now", power_measurements
                    ),
                    "energy_current_hour_kwh": _latest_numeric(
                        forecast_cfg.get("energy_current_hour_entity_id"),
                        "forecast_energy_current_hour",
                        kwh_measurements,
                    ),
                    "energy_next_hour_kwh": _latest_numeric(
                        forecast_cfg.get("energy_next_hour_entity_id"),
                        "forecast_energy_next_hour",
                        kwh_measurements,
                    ),
                    "energy_production_today_kwh": _latest_numeric(
                        forecast_cfg.get("energy_production_today_entity_id"),
                        "forecast_energy_today",
                        kwh_measurements,
                    ),
                    "energy_production_today_remaining_kwh": _latest_numeric(
                        forecast_cfg.get("energy_production_today_remaining_entity_id"),
                        "forecast_energy_today_remaining",
                        kwh_measurements,
                    ),
                    "energy_production_tomorrow_kwh": _latest_numeric(
                        forecast_cfg.get("energy_production_tomorrow_entity_id"),
                        "forecast_energy_tomorrow",
                        kwh_measurements,
                    ),
                    "peak_time_today": _latest_raw(
                        forecast_cfg.get("power_highest_peak_time_today_entity_id"),
                        "forecast_peak_time_today",
                        state_measurements,
                    ),
                    "peak_time_tomorrow": _latest_raw(
                        forecast_cfg.get("power_highest_peak_time_tomorrow_entity_id"),
                        "forecast_peak_time_tomorrow",
                        state_measurements,
                    ),
                }
            )
            forecast_payload["peak_time_today_hhmm"] = self._iso_to_display_hhmm(forecast_payload.get("peak_time_today"))
            forecast_payload["peak_time_tomorrow_hhmm"] = self._iso_to_display_hhmm(
                forecast_payload.get("peak_time_tomorrow")
            )
            forecast_payload["available"] = any(
                forecast_payload.get(key) is not None
                for key in (
                    "power_now_w",
                    "energy_current_hour_kwh",
                    "energy_next_hour_kwh",
                    "energy_production_today_kwh",
                    "energy_production_today_remaining_kwh",
                    "energy_production_tomorrow_kwh",
                    "peak_time_today",
                    "peak_time_tomorrow",
                )
            )

        projection = None
        if is_today:
            interval_minutes = self._parse_influx_interval_to_minutes(history_interval, default_minutes=15)
            load_profile = {}
            pv_profile = {}
            if energy_cfg.get("house_load_power_entity_id"):
                try:
                    load_profile = self._query_recent_slot_profile_by_day_type(
                        influx,
                        energy_cfg.get("house_load_power_entity_id"),
                        tzinfo,
                        target_date=now_local.date(),
                        days=28,
                        interval=history_interval,
                        measurement_candidates=power_measurements,
                    )
                except (HTTPException, RequestException, ValueError, TypeError) as exc:
                    self._logger.warning("Battery projection load profile query failed: %s", exc)
            if energy_cfg.get("pv_power_total_entity_id"):
                try:
                    pv_profile = self._query_recent_slot_profile_by_day_type(
                        influx,
                        energy_cfg.get("pv_power_total_entity_id"),
                        tzinfo,
                        target_date=now_local.date(),
                        days=28,
                        interval=history_interval,
                        measurement_candidates=power_measurements,
                    )
                except (HTTPException, RequestException, ValueError, TypeError) as exc:
                    self._logger.warning("Battery projection PV profile query failed: %s", exc)

            projection = self._build_hybrid_battery_projection(
                now_local=now_local,
                soc_percent=clamped_soc,
                avg_power_w=avg_power_w,
                battery_cfg=battery_cfg,
                tzinfo=tzinfo,
                interval_minutes=interval_minutes,
                current_energy=current_energy,
                forecast_payload=forecast_payload,
                load_profile=load_profile,
                pv_profile=pv_profile,
            )
            if projection is None:
                projection = self._build_battery_projection(now_local, clamped_soc, avg_power_w, battery_cfg, tzinfo)
        else:
            projection = {
                "method": "none",
                "confidence": "low",
                "state": "historical",
                "eta_to_full_minutes": None,
                "eta_to_reserve_minutes": None,
                "eta_to_full_at": None,
                "eta_to_reserve_at": None,
                "points": [],
            }

        return {
            "enabled": True,
            "configured": True,
            "date": selected_date,
            "is_today": is_today,
            "timezone": str(tzinfo),
            "history": {
                "interval": history_interval,
                "soc_entity_id": battery_cfg["soc_entity_id"],
                "power_entity_id": battery_cfg["power_entity_id"],
                "points": history_points,
            },
            "status": {
                "soc_percent": clamped_soc,
                "battery_power_w": battery_power_w,
                "battery_state": battery_state,
                "avg_battery_power_w": round(avg_power_w, 3) if avg_power_w is not None else None,
                "eta_smoothing_minutes": battery_cfg["eta_smoothing_minutes"],
                "min_power_threshold_w": battery_cfg["min_power_threshold_w"],
                "usable_capacity_kwh": usable_capacity_kwh,
                "reserve_soc_percent": reserve_soc_percent,
                "stored_kwh": stored_kwh,
                "available_to_reserve_kwh": available_to_reserve_kwh,
                "remaining_to_full_kwh": remaining_to_full_kwh,
                "last_soc_time": latest_soc.get("time") if latest_soc else None,
                "last_power_time": latest_power.get("time") if latest_power else None,
            },
            "projection": projection,
            "current_energy": current_energy,
            "forecast_solar": forecast_payload,
        }
