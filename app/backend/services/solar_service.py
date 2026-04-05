import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, Optional

logger = logging.getLogger("uvicorn.error")


def _clamp(value: float, min_value: float, max_value: float) -> float:
    return max(min_value, min(max_value, value))


def _to_hhmm(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    return dt.strftime("%H:%M")


class SolarService:
    def __init__(
        self,
        get_influx_cfg_fn,
        get_forecast_solar_cfg_fn,
        safe_query_entity_last_value_fn,
        get_energy_entities_cfg_fn=None,
        query_entity_series_fn=None,
        parse_influx_interval_to_minutes_fn=None,
        aggregate_power_points_fn=None,
        get_local_tz_fn=None,
        history_file_path_fn=None,
        now_fn=None,
        logger=None,
    ):
        self.get_influx_cfg = get_influx_cfg_fn
        self.get_forecast_solar_cfg = get_forecast_solar_cfg_fn
        self.get_energy_entities_cfg = get_energy_entities_cfg_fn or (lambda cfg: {})
        self.query_entity_series = query_entity_series_fn or (lambda *args, **kwargs: [])
        self.parse_influx_interval_to_minutes = (
            parse_influx_interval_to_minutes_fn or (lambda interval, default_minutes=15: default_minutes)
        )
        self.aggregate_power_points = aggregate_power_points_fn or (
            lambda points, interval_minutes=15, bucket="day", tzinfo=None: {}
        )
        self.get_local_tz = get_local_tz_fn or (lambda tz_name=None: datetime.now().astimezone().tzinfo)
        self.get_history_file_path = history_file_path_fn or (lambda: None)
        self.now_fn = now_fn or (lambda tzinfo=None: datetime.now(tzinfo))
        self.safe_query_entity_last_value = safe_query_entity_last_value_fn
        self.logger = logger or logging.getLogger("uvicorn.error")

    def _load_history(self) -> Dict[str, Dict[str, Any]]:
        path = self.get_history_file_path()
        if not path:
            return {}
        file_path = Path(path)
        if not file_path.exists():
            return {}
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _save_history(self, history: Dict[str, Dict[str, Any]]) -> None:
        path = self.get_history_file_path()
        if not path:
            return
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as handle:
            json.dump(history, handle, ensure_ascii=True, indent=2, sort_keys=True)

    def _summarize_history(self, history: Dict[str, Dict[str, Any]], today_key: str) -> Dict[str, Any]:
        completed = []
        for date_key, entry in sorted(history.items()):
            if date_key >= today_key:
                continue
            actual_total = entry.get("actual_total_kwh")
            forecast_total = entry.get("forecast_total_kwh")
            if actual_total is None or forecast_total in (None, 0):
                continue
            try:
                ratio = float(actual_total) / float(forecast_total)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            completed.append(
                {
                    "date": date_key,
                    "actual_total_kwh": round(float(actual_total), 5),
                    "forecast_total_kwh": round(float(forecast_total), 5),
                    "ratio": round(ratio, 5),
                }
            )

        ratios = [entry["ratio"] for entry in completed]
        median_ratio = round(median(ratios), 5) if ratios else None
        avg_ratio = round(sum(ratios) / len(ratios), 5) if ratios else None
        recent = completed[-7:]

        return {
            "days_tracked": len(completed),
            "median_ratio": median_ratio,
            "avg_ratio": avg_ratio,
            "last_completed_date": recent[-1]["date"] if recent else None,
            "recent_days": recent,
        }

    def _read_numeric_entity(
        self,
        influx: Dict[str, Any],
        entity_id: Optional[str],
        label: str,
        measurement_candidates,
        tzinfo=None,
    ) -> Optional[float]:
        if not entity_id:
            return None
        record = self.safe_query_entity_last_value(
            influx,
            entity_id,
            tzinfo=tzinfo,
            numeric=True,
            label=label,
            measurement_candidates=measurement_candidates,
        )
        return None if not record else record.get("value")

    def _read_raw_entity(
        self,
        influx: Dict[str, Any],
        entity_id: Optional[str],
        label: str,
        measurement_candidates,
        tzinfo=None,
    ) -> Optional[str]:
        if not entity_id:
            return None
        record = self.safe_query_entity_last_value(
            influx,
            entity_id,
            tzinfo=tzinfo,
            numeric=False,
            label=label,
            measurement_candidates=measurement_candidates,
        )
        return None if not record else record.get("raw_value")

    def get_solar_forecast(self, cfg):
        solar_cfg = self.get_forecast_solar_cfg(cfg)
        influx = self.get_influx_cfg(cfg)
        energy_cfg = self.get_energy_entities_cfg(cfg)
        tzinfo = self.get_local_tz(influx.get("timezone"))
        if not solar_cfg.get("enabled"):
            return {"enabled": False}

        now_local = self.now_fn(tzinfo)
        date_str = now_local.strftime("%Y-%m-%d")
        interval = influx.get("interval", "15m")
        interval_minutes = self.parse_influx_interval_to_minutes(interval, default_minutes=15)

        res = {
            "enabled": True,
            "date": date_str,
            "status": {},
            "actual": {
                "pv_power_entity_id": energy_cfg.get("pv_power_total_entity_id"),
                "power_now_w": None,
                "production_today_kwh": None,
            },
            "comparison": {
                "forecast_so_far_kwh": None,
                "delta_so_far_kwh": None,
                "power_delta_w": None,
                "live_ratio": None,
                "historical_bias_ratio": None,
                "effective_bias_ratio": None,
                "adjusted_projection_today_kwh": None,
                "projection_delta_to_forecast_kwh": None,
            },
            "history": {
                "days_tracked": 0,
                "median_ratio": None,
                "avg_ratio": None,
                "last_completed_date": None,
                "recent_days": [],
            },
        }

        power_measurements = ["W", "kW"]
        energy_measurements = ["kWh", "Wh"]
        state_measurements = ["state"]

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
            if not entity_id:
                continue
            is_numeric = "peak" not in key
            if key == "power_now":
                measurement_candidates = power_measurements
            elif key.startswith("energy_") or key.startswith("production_"):
                measurement_candidates = energy_measurements
            else:
                measurement_candidates = state_measurements
            val = self.safe_query_entity_last_value(
                influx,
                entity_id,
                tzinfo=tzinfo,
                numeric=is_numeric,
                label=f"solar_{key}",
                measurement_candidates=measurement_candidates,
            )
            if val:
                res["status"][key] = val.get("value") if is_numeric else val.get("raw_value")
            else:
                res["status"][key] = None

        actual_power_now = self._read_numeric_entity(
            influx,
            energy_cfg.get("pv_power_total_entity_id"),
            "pv_actual_power_now",
            power_measurements,
            tzinfo=tzinfo,
        )
        res["actual"]["power_now_w"] = actual_power_now

        pv_points = []
        if energy_cfg.get("pv_power_total_entity_id"):
            try:
                start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                pv_points = self.query_entity_series(
                    influx,
                    energy_cfg.get("pv_power_total_entity_id"),
                    start_local.astimezone(timezone.utc),
                    now_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=power_measurements,
                )
            except Exception as exc:
                self.logger.warning("Solar actual PV query failed: %s", exc)
                pv_points = []

        if pv_points:
            daily_totals = self.aggregate_power_points(
                pv_points,
                interval_minutes,
                bucket="day",
                tzinfo=tzinfo,
            )
            res["actual"]["production_today_kwh"] = daily_totals.get(date_str)
            res["actual"]["samples_today"] = len(pv_points)

        forecast_total = res["status"].get("production_today")
        forecast_remaining = res["status"].get("production_today_remaining")
        forecast_power_now = res["status"].get("power_now")
        actual_total = res["actual"].get("production_today_kwh")

        forecast_so_far = None
        if forecast_total is not None and forecast_remaining is not None:
            forecast_so_far = max(0.0, float(forecast_total) - float(forecast_remaining))

        live_ratio = None
        if actual_total is not None and forecast_so_far not in (None, 0):
            live_ratio = round(float(actual_total) / float(forecast_so_far), 5)

        history = self._load_history()
        history_summary = self._summarize_history(history, date_str)
        history_bias = history_summary.get("median_ratio")

        effective_bias = None
        if history_bias is not None and live_ratio is not None:
            effective_bias = round(_clamp((float(history_bias) * 0.6) + (float(live_ratio) * 0.4), 0.25, 2.5), 5)
        elif live_ratio is not None:
            effective_bias = round(_clamp(float(live_ratio), 0.25, 2.5), 5)
        elif history_bias is not None:
            effective_bias = round(_clamp(float(history_bias), 0.25, 2.5), 5)

        adjusted_projection = None
        if actual_total is not None and forecast_remaining is not None:
            projection_bias = effective_bias if effective_bias is not None else 1.0
            adjusted_projection = round(float(actual_total) + (float(forecast_remaining) * projection_bias), 5)
        elif forecast_total is not None and effective_bias is not None:
            adjusted_projection = round(float(forecast_total) * float(effective_bias), 5)

        projection_gap = None
        if adjusted_projection is not None and forecast_total is not None:
            projection_gap = round(float(adjusted_projection) - float(forecast_total), 5)

        power_delta = None
        if actual_power_now is not None and forecast_power_now is not None:
            power_delta = round(float(actual_power_now) - float(forecast_power_now), 3)

        delta_so_far = None
        if actual_total is not None and forecast_so_far is not None:
            delta_so_far = round(float(actual_total) - float(forecast_so_far), 5)

        res["comparison"].update(
            {
                "forecast_so_far_kwh": round(float(forecast_so_far), 5) if forecast_so_far is not None else None,
                "delta_so_far_kwh": delta_so_far,
                "power_delta_w": power_delta,
                "live_ratio": live_ratio,
                "historical_bias_ratio": history_bias,
                "effective_bias_ratio": effective_bias,
                "adjusted_projection_today_kwh": adjusted_projection,
                "projection_delta_to_forecast_kwh": projection_gap,
            }
        )
        res["history"] = history_summary

        history[date_str] = {
            "updated_at": now_local.isoformat(),
            "actual_total_kwh": actual_total,
            "actual_power_now_w": actual_power_now,
            "forecast_power_now_w": forecast_power_now,
            "forecast_so_far_kwh": forecast_so_far,
            "forecast_remaining_kwh": forecast_remaining,
            "forecast_total_kwh": forecast_total,
            "adjusted_projection_today_kwh": adjusted_projection,
        }
        self._save_history(history)

        peak_today_raw = res["status"].get("peak_today")
        peak_tomorrow_raw = res["status"].get("peak_tomorrow")
        if peak_today_raw:
            res["status"]["peak_time_today_hhmm"] = _to_hhmm(peak_today_raw)
        if peak_tomorrow_raw:
            res["status"]["peak_time_tomorrow_hhmm"] = _to_hhmm(peak_tomorrow_raw)

        return res
