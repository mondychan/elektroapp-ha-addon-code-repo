import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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


def _empty_hourly_list() -> List[Optional[float]]:
    return [None] * 24


def _serialize_hourly_map(hourly_map: Optional[Dict[int, float]]) -> List[Optional[float]]:
    result = _empty_hourly_list()
    if not isinstance(hourly_map, dict):
        return result
    for hour, value in hourly_map.items():
        try:
            idx = int(hour)
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx > 23 or value is None:
            continue
        result[idx] = round(float(value), 5)
    return result


def _deserialize_hourly_map(payload: Any) -> Dict[int, float]:
    hourly: Dict[int, float] = {}
    if isinstance(payload, list):
        for idx, value in enumerate(payload[:24]):
            if value is None:
                continue
            try:
                hourly[idx] = round(float(value), 5)
            except (TypeError, ValueError):
                continue
        return hourly

    if isinstance(payload, dict):
        for key, value in payload.items():
            try:
                idx = int(key)
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if 0 <= idx <= 23:
                hourly[idx] = round(numeric, 5)
    return hourly


def _power_value_to_kwh(value: float, interval_minutes: int, unit: Optional[str] = None) -> float:
    interval_hours = max(interval_minutes, 1) / 60.0
    unit_lower = (unit or "").lower()
    if unit_lower == "w":
        return (value / 1000.0) * interval_hours
    if unit_lower == "kw":
        return value * interval_hours
    if abs(value) <= 50:
        return value * interval_hours
    return (value / 1000.0) * interval_hours


def _default_get_local_tz(tz_name=None):
    try:
        return ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return datetime.now().astimezone().tzinfo


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
        history_backfill_days: int = 365,
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
        self.get_local_tz = get_local_tz_fn or _default_get_local_tz
        self.get_history_file_path = history_file_path_fn or (lambda: None)
        self.now_fn = now_fn or (lambda tzinfo=None: datetime.now(tzinfo))
        self.safe_query_entity_last_value = safe_query_entity_last_value_fn
        self.logger = logger or logging.getLogger("uvicorn.error")
        self.history_backfill_days = max(0, min(int(history_backfill_days or 0), 365))
        self._backfill_completed_for_date: Optional[str] = None

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

    def _point_time_to_local(self, point: Dict[str, Any], tzinfo) -> Optional[datetime]:
        time_raw = point.get("time")
        if isinstance(time_raw, str):
            try:
                dt_local = datetime.fromisoformat(time_raw)
                if dt_local.tzinfo is None and tzinfo is not None:
                    dt_local = dt_local.replace(tzinfo=tzinfo)
                return dt_local if tzinfo is None else dt_local.astimezone(tzinfo)
            except ValueError:
                pass

        time_utc_raw = point.get("time_utc")
        if isinstance(time_utc_raw, str):
            try:
                dt_utc = datetime.fromisoformat(time_utc_raw.replace("Z", "+00:00"))
                return dt_utc if tzinfo is None else dt_utc.astimezone(tzinfo)
            except ValueError:
                return None
        return None

    def _normalize_energy_value(self, value: Any, unit: Optional[str]) -> Optional[float]:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        unit_lower = (unit or "").lower()
        if unit_lower == "wh":
            numeric /= 1000.0
        return round(numeric, 5)

    def _collect_daily_energy_stats(self, points, tzinfo, *, day_shift: int = 0) -> Dict[str, Dict[str, Any]]:
        daily: Dict[str, Dict[str, Any]] = {}
        for point in points or []:
            dt_local = self._point_time_to_local(point, tzinfo)
            if dt_local is None:
                continue
            normalized = self._normalize_energy_value(point.get("value"), point.get("unit"))
            if normalized is None:
                continue
            target_dt = dt_local + timedelta(days=day_shift)
            day_key = target_dt.strftime("%Y-%m-%d")
            bucket = daily.setdefault(day_key, {"last": None, "max": None, "samples": 0})
            bucket["last"] = normalized
            bucket["max"] = normalized if bucket["max"] is None else max(bucket["max"], normalized)
            bucket["samples"] += 1
        return daily

    def _collect_hourly_energy_stats(self, points, tzinfo, *, hour_shift: int = 0) -> Dict[str, Dict[int, float]]:
        daily: Dict[str, Dict[int, float]] = {}
        for point in points or []:
            dt_local = self._point_time_to_local(point, tzinfo)
            if dt_local is None:
                continue
            normalized = self._normalize_energy_value(point.get("value"), point.get("unit"))
            if normalized is None:
                continue
            target_dt = dt_local + timedelta(hours=hour_shift)
            day_key = target_dt.strftime("%Y-%m-%d")
            daily.setdefault(day_key, {})[target_dt.hour] = normalized
        return daily

    def _aggregate_actual_hourly_kwh(self, points, interval_minutes: int, tzinfo) -> Dict[str, Dict[int, float]]:
        daily: Dict[str, Dict[int, float]] = {}
        for point in points or []:
            raw_value = point.get("value")
            if raw_value is None:
                continue
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                continue
            dt_local = self._point_time_to_local(point, tzinfo)
            if dt_local is None:
                continue
            day_key = dt_local.strftime("%Y-%m-%d")
            day_bucket = daily.setdefault(day_key, {})
            day_bucket[dt_local.hour] = round(
                day_bucket.get(dt_local.hour, 0.0)
                + _power_value_to_kwh(value, interval_minutes, point.get("unit")),
                5,
            )
        return daily

    def _pick_forecast_value(self, daily_stats: Optional[Dict[str, Any]]) -> tuple[Optional[float], Optional[str]]:
        if not isinstance(daily_stats, dict):
            return None, None
        if daily_stats.get("last") is not None:
            return round(float(daily_stats["last"]), 5), "last"
        if daily_stats.get("max") is not None:
            return round(float(daily_stats["max"]), 5), "max"
        return None, None

    def _summarize_history(self, history: Dict[str, Dict[str, Any]], today_key: str) -> Dict[str, Any]:
        completed = []
        hourly_slots_tracked = 0
        cache_days = 0
        for date_key, entry in sorted(history.items()):
            if date_key >= today_key:
                continue
            cache_days += 1
            forecast_hourly = _deserialize_hourly_map(entry.get("forecast_hourly_kwh_by_hour"))
            actual_hourly = _deserialize_hourly_map(entry.get("actual_hourly_kwh_by_hour"))
            hourly_slots_tracked += sum(
                1
                for hour in range(24)
                if actual_hourly.get(hour) is not None and forecast_hourly.get(hour) not in (None, 0)
            )
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
            "cache_days": cache_days,
            "hourly_slots_tracked": hourly_slots_tracked,
            "median_ratio": median_ratio,
            "avg_ratio": avg_ratio,
            "last_completed_date": recent[-1]["date"] if recent else None,
            "recent_days": recent,
        }

    def _build_hourly_history_stats(self, history: Dict[str, Dict[str, Any]], today_key: str) -> Dict[str, Any]:
        hourly_ratios: Dict[int, List[float]] = {hour: [] for hour in range(24)}
        hourly_shares: Dict[int, List[float]] = {hour: [] for hour in range(24)}
        tracked_days = 0

        for date_key, entry in sorted(history.items()):
            if date_key >= today_key:
                continue
            actual_hourly = _deserialize_hourly_map(entry.get("actual_hourly_kwh_by_hour"))
            forecast_hourly = _deserialize_hourly_map(entry.get("forecast_hourly_kwh_by_hour"))
            forecast_total = entry.get("forecast_total_kwh")
            has_any = False
            for hour in range(24):
                actual_value = actual_hourly.get(hour)
                forecast_value = forecast_hourly.get(hour)
                if actual_value is None or forecast_value in (None, 0):
                    continue
                hourly_ratios[hour].append(float(actual_value) / float(forecast_value))
                has_any = True
            if forecast_total not in (None, 0):
                try:
                    total_float = float(forecast_total)
                except (TypeError, ValueError):
                    total_float = None
                if total_float:
                    for hour, value in forecast_hourly.items():
                        if value is None or value <= 0:
                            continue
                        hourly_shares[hour].append(float(value) / total_float)
            if has_any:
                tracked_days += 1

        bias_by_hour = _empty_hourly_list()
        share_by_hour = _empty_hourly_list()
        for hour in range(24):
            if hourly_ratios[hour]:
                bias_by_hour[hour] = round(_clamp(median(hourly_ratios[hour]), 0.25, 2.5), 5)
            if hourly_shares[hour]:
                share_by_hour[hour] = round(median(hourly_shares[hour]), 5)

        total_share = sum(value for value in share_by_hour if value is not None)
        if total_share > 0:
            share_by_hour = [
                round((value / total_share), 5) if value is not None else None
                for value in share_by_hour
            ]

        return {
            "bias_by_hour": bias_by_hour,
            "share_by_hour": share_by_hour,
            "days_tracked": tracked_days,
        }

    def _weighted_average(self, values: List[Optional[float]], weights: List[Optional[float]]) -> Optional[float]:
        pairs = []
        for idx, value in enumerate(values):
            if value is None:
                continue
            weight = weights[idx] if idx < len(weights) else None
            if weight is None or weight <= 0:
                continue
            pairs.append((float(value), float(weight)))
        if not pairs:
            return None
        total_weight = sum(weight for _, weight in pairs)
        if total_weight <= 0:
            return None
        return round(sum(value * weight for value, weight in pairs) / total_weight, 5)

    def _read_numeric_entity(self, influx: Dict[str, Any], entity_id: Optional[str], label: str, measurement_candidates, tzinfo=None) -> Optional[float]:
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

    def _read_raw_entity(self, influx: Dict[str, Any], entity_id: Optional[str], label: str, measurement_candidates, tzinfo=None) -> Optional[str]:
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

    def _backfill_history_from_influx(
        self,
        history: Dict[str, Dict[str, Any]],
        influx: Dict[str, Any],
        solar_cfg: Dict[str, Any],
        energy_cfg: Dict[str, Any],
        tzinfo,
        now_local: datetime,
        interval: str,
        interval_minutes: int,
    ) -> Dict[str, Dict[str, Any]]:
        today_key = now_local.strftime("%Y-%m-%d")
        if self.history_backfill_days <= 0 or self._backfill_completed_for_date == today_key:
            return history

        power_measurements = ["W", "kW"]
        energy_measurements = ["kWh", "Wh"]
        today_start_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        history_start_local = today_start_local - timedelta(days=self.history_backfill_days)
        history_end_local = today_start_local
        dirty = False

        actuals_by_day: Dict[str, float] = {}
        actual_hourly_by_day: Dict[str, Dict[int, float]] = {}
        forecast_today_stats: Dict[str, Dict[str, Any]] = {}
        forecast_tomorrow_prev_day_stats: Dict[str, Dict[str, Any]] = {}
        forecast_current_hour_by_day: Dict[str, Dict[int, float]] = {}
        forecast_next_hour_by_day: Dict[str, Dict[int, float]] = {}

        actual_entity_id = energy_cfg.get("pv_power_total_entity_id")
        if actual_entity_id:
            try:
                actual_points = self.query_entity_series(
                    influx,
                    actual_entity_id,
                    history_start_local.astimezone(timezone.utc),
                    history_end_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=power_measurements,
                )
                actuals_by_day = self.aggregate_power_points(actual_points, interval_minutes, bucket="day", tzinfo=tzinfo)
                actual_hourly_by_day = self._aggregate_actual_hourly_kwh(actual_points, interval_minutes, tzinfo)
            except Exception as exc:
                self.logger.warning("Solar history actual backfill failed: %s", exc)

        production_today_entity_id = solar_cfg.get("energy_production_today_entity_id")
        if production_today_entity_id:
            try:
                forecast_today_points = self.query_entity_series(
                    influx,
                    production_today_entity_id,
                    history_start_local.astimezone(timezone.utc),
                    history_end_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=energy_measurements,
                )
                forecast_today_stats = self._collect_daily_energy_stats(forecast_today_points, tzinfo)
            except Exception as exc:
                self.logger.warning("Solar history production_today backfill failed: %s", exc)

        production_tomorrow_entity_id = solar_cfg.get("energy_production_tomorrow_entity_id")
        if production_tomorrow_entity_id:
            try:
                forecast_tomorrow_points = self.query_entity_series(
                    influx,
                    production_tomorrow_entity_id,
                    (history_start_local - timedelta(days=1)).astimezone(timezone.utc),
                    history_end_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=energy_measurements,
                )
                forecast_tomorrow_prev_day_stats = self._collect_daily_energy_stats(
                    forecast_tomorrow_points,
                    tzinfo,
                    day_shift=1,
                )
            except Exception as exc:
                self.logger.warning("Solar history production_tomorrow backfill failed: %s", exc)

        current_hour_entity_id = solar_cfg.get("energy_current_hour_entity_id")
        if current_hour_entity_id:
            try:
                current_hour_points = self.query_entity_series(
                    influx,
                    current_hour_entity_id,
                    history_start_local.astimezone(timezone.utc),
                    history_end_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=energy_measurements,
                )
                forecast_current_hour_by_day = self._collect_hourly_energy_stats(current_hour_points, tzinfo)
            except Exception as exc:
                self.logger.warning("Solar history current_hour backfill failed: %s", exc)

        next_hour_entity_id = solar_cfg.get("energy_next_hour_entity_id")
        if next_hour_entity_id:
            try:
                next_hour_points = self.query_entity_series(
                    influx,
                    next_hour_entity_id,
                    (history_start_local - timedelta(hours=1)).astimezone(timezone.utc),
                    history_end_local.astimezone(timezone.utc),
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=energy_measurements,
                )
                forecast_next_hour_by_day = self._collect_hourly_energy_stats(next_hour_points, tzinfo, hour_shift=1)
            except Exception as exc:
                self.logger.warning("Solar history next_hour backfill failed: %s", exc)

        current_day = history_start_local
        while current_day < history_end_local:
            day_key = current_day.strftime("%Y-%m-%d")
            entry = history.get(day_key, {}) if isinstance(history.get(day_key), dict) else {}
            updated_entry = dict(entry)

            actual_total = actuals_by_day.get(day_key)
            if actual_total is not None:
                updated_entry["actual_total_kwh"] = round(float(actual_total), 5)
            updated_entry["actual_hourly_kwh_by_hour"] = _serialize_hourly_map(actual_hourly_by_day.get(day_key, {}))

            same_day_stats = forecast_today_stats.get(day_key)
            if same_day_stats:
                if same_day_stats.get("last") is not None:
                    updated_entry["forecast_today_last_kwh"] = round(float(same_day_stats["last"]), 5)
                if same_day_stats.get("max") is not None:
                    updated_entry["forecast_today_max_kwh"] = round(float(same_day_stats["max"]), 5)

            prev_day_tomorrow_stats = forecast_tomorrow_prev_day_stats.get(day_key)
            if prev_day_tomorrow_stats:
                if prev_day_tomorrow_stats.get("last") is not None:
                    updated_entry["forecast_tomorrow_prev_day_last_kwh"] = round(float(prev_day_tomorrow_stats["last"]), 5)
                if prev_day_tomorrow_stats.get("max") is not None:
                    updated_entry["forecast_tomorrow_prev_day_max_kwh"] = round(float(prev_day_tomorrow_stats["max"]), 5)

            combined_hourly_forecast = dict(forecast_next_hour_by_day.get(day_key, {}))
            combined_hourly_forecast.update(forecast_current_hour_by_day.get(day_key, {}))
            updated_entry["forecast_hourly_kwh_by_hour"] = _serialize_hourly_map(combined_hourly_forecast)

            chosen_forecast = None
            chosen_source = None
            prev_day_value, prev_day_pick = self._pick_forecast_value(prev_day_tomorrow_stats)
            if prev_day_value is not None:
                chosen_forecast = prev_day_value
                chosen_source = f"production_tomorrow_prev_day_{prev_day_pick}"
            else:
                same_day_value, same_day_pick = self._pick_forecast_value(same_day_stats)
                if same_day_value is not None:
                    chosen_forecast = same_day_value
                    chosen_source = f"production_today_{same_day_pick}"

            if chosen_forecast is not None:
                updated_entry["forecast_total_kwh"] = round(float(chosen_forecast), 5)
                updated_entry["forecast_total_source"] = chosen_source

            if updated_entry != entry:
                updated_entry["backfilled_at"] = now_local.isoformat()
                history[day_key] = updated_entry
                dirty = True

            current_day += timedelta(days=1)

        if dirty:
            self._save_history(history)
        self._backfill_completed_for_date = today_key
        return history

    def _build_profile_from_total(
        self,
        total_kwh: Optional[float],
        share_by_hour: List[Optional[float]],
        *,
        start_hour: int = 0,
        end_hour: int = 23,
    ) -> List[Optional[float]]:
        profile = _empty_hourly_list()
        if total_kwh is None or total_kwh < 0:
            return profile
        scoped_shares = []
        for hour in range(start_hour, end_hour + 1):
            value = share_by_hour[hour] if hour < len(share_by_hour) else None
            if value is not None and value > 0:
                scoped_shares.append((hour, float(value)))
        if not scoped_shares:
            return profile
        share_total = sum(value for _, value in scoped_shares)
        if share_total <= 0:
            return profile
        for hour, value in scoped_shares:
            profile[hour] = round(float(total_kwh) * (value / share_total), 5)
        return profile

    def _apply_hourly_bias(
        self,
        raw_profile_kwh_by_hour: List[Optional[float]],
        bias_by_hour: List[Optional[float]],
        fallback_bias: Optional[float],
    ) -> List[Optional[float]]:
        adjusted = _empty_hourly_list()
        for hour in range(24):
            raw_value = raw_profile_kwh_by_hour[hour] if hour < len(raw_profile_kwh_by_hour) else None
            if raw_value is None:
                continue
            bias = bias_by_hour[hour] if hour < len(bias_by_hour) else None
            if bias is None:
                bias = fallback_bias
            adjusted[hour] = round(float(raw_value) * float(bias if bias is not None else 1.0), 5)
        return adjusted

    def _hourly_profile_to_horizon_watts(
        self,
        now_local: datetime,
        today_profile_kwh_by_hour: List[Optional[float]],
        tomorrow_profile_kwh_by_hour: List[Optional[float]],
        *,
        horizon_hours: int,
        anchor_watts: Dict[int, Optional[float]],
    ) -> List[Optional[float]]:
        horizon: List[Optional[float]] = []
        base_time = now_local.replace(minute=0, second=0, microsecond=0)
        for offset in range(1, horizon_hours + 1):
            target_dt = base_time + timedelta(hours=offset)
            if target_dt.date() == now_local.date():
                kwh_value = today_profile_kwh_by_hour[target_dt.hour] if target_dt.hour < 24 else None
            else:
                kwh_value = tomorrow_profile_kwh_by_hour[target_dt.hour] if target_dt.hour < 24 else None
            watt_value = round(float(kwh_value) * 1000.0, 3) if kwh_value is not None else None
            anchor_value = anchor_watts.get(offset)
            horizon.append(round(float(anchor_value), 3) if anchor_value is not None else watt_value)
        return horizon

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
                "model_version": "v2_hourly_bias",
                "forecast_so_far_kwh": None,
                "delta_so_far_kwh": None,
                "power_delta_w": None,
                "live_ratio": None,
                "historical_bias_ratio": None,
                "remaining_hourly_bias_ratio": None,
                "effective_bias_ratio": None,
                "adjusted_projection_today_kwh": None,
                "projection_delta_to_forecast_kwh": None,
                "adjusted_projection_tomorrow_kwh": None,
                "projection_delta_to_forecast_tomorrow_kwh": None,
                "adjusted_current_hour_kwh": None,
                "adjusted_next_hour_kwh": None,
                "adjusted_today_hourly_profile_kwh_by_hour": _empty_hourly_list(),
                "adjusted_tomorrow_hourly_profile_kwh_by_hour": _empty_hourly_list(),
                "future_profile_source": None,
            },
            "history": {
                "days_tracked": 0,
                "cache_days": 0,
                "hourly_slots_tracked": 0,
                "median_ratio": None,
                "avg_ratio": None,
                "last_completed_date": None,
                "recent_days": [],
                "profile_sources_available": {},
            },
        }

        power_measurements = ["W", "kW"]
        energy_measurements = ["kWh", "Wh"]
        state_measurements = ["state"]

        entities = {
            "power_now": solar_cfg.get("power_now_entity_id"),
            "power_next_hour": solar_cfg.get("power_next_hour_entity_id"),
            "power_next_12hours": solar_cfg.get("power_next_12hours_entity_id"),
            "power_next_24hours": solar_cfg.get("power_next_24hours_entity_id"),
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
            if key.startswith("power_"):
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
            res["status"][key] = val.get("value") if val and is_numeric else (val.get("raw_value") if val else None)

        actual_power_now = self._read_numeric_entity(
            influx,
            energy_cfg.get("pv_power_total_entity_id"),
            "pv_actual_power_now",
            power_measurements,
            tzinfo=tzinfo,
        )
        res["actual"]["power_now_w"] = actual_power_now

        pv_points = []
        today_actual_hourly = {}
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
            daily_totals = self.aggregate_power_points(pv_points, interval_minutes, bucket="day", tzinfo=tzinfo)
            today_actual_hourly = self._aggregate_actual_hourly_kwh(pv_points, interval_minutes, tzinfo).get(date_str, {})
            res["actual"]["production_today_kwh"] = daily_totals.get(date_str)
            res["actual"]["samples_today"] = len(pv_points)

        forecast_total = res["status"].get("production_today")
        forecast_remaining = res["status"].get("production_today_remaining")
        forecast_power_now = res["status"].get("power_now")
        forecast_current_hour = res["status"].get("energy_current_hour")
        forecast_next_hour = res["status"].get("energy_next_hour")
        forecast_tomorrow_total = res["status"].get("production_tomorrow")
        actual_total = res["actual"].get("production_today_kwh")

        forecast_so_far = None
        if forecast_total is not None and forecast_remaining is not None:
            forecast_so_far = max(0.0, float(forecast_total) - float(forecast_remaining))

        live_ratio = None
        if actual_total is not None and forecast_so_far not in (None, 0):
            live_ratio = round(float(actual_total) / float(forecast_so_far), 5)

        history = self._load_history()
        history = self._backfill_history_from_influx(
            history,
            influx,
            solar_cfg,
            energy_cfg,
            tzinfo,
            now_local,
            interval,
            interval_minutes,
        )
        history_summary = self._summarize_history(history, date_str)
        history_hourly = self._build_hourly_history_stats(history, date_str)

        history_bias = history_summary.get("median_ratio")
        hourly_bias_by_hour = history_hourly.get("bias_by_hour") or _empty_hourly_list()
        hourly_share_by_hour = history_hourly.get("share_by_hour") or _empty_hourly_list()
        current_hour_idx = now_local.hour
        next_hour_idx = (current_hour_idx + 1) % 24

        remaining_weights = _empty_hourly_list()
        for hour in range(current_hour_idx, 24):
            remaining_weights[hour] = hourly_share_by_hour[hour]
        remaining_hourly_bias = self._weighted_average(hourly_bias_by_hour, remaining_weights)
        if remaining_hourly_bias is None:
            remaining_hourly_bias = history_bias

        effective_bias = None
        if history_bias is not None and live_ratio is not None and remaining_hourly_bias is not None:
            effective_bias = round(
                _clamp(
                    (float(live_ratio) * 0.4)
                    + (float(history_bias) * 0.3)
                    + (float(remaining_hourly_bias) * 0.3),
                    0.25,
                    2.5,
                ),
                5,
            )
        elif live_ratio is not None:
            effective_bias = round(_clamp(float(live_ratio), 0.25, 2.5), 5)
        elif remaining_hourly_bias is not None:
            effective_bias = round(_clamp(float(remaining_hourly_bias), 0.25, 2.5), 5)
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

        adjusted_current_hour = None
        if forecast_current_hour is not None:
            hour_bias = hourly_bias_by_hour[current_hour_idx] if hourly_bias_by_hour[current_hour_idx] is not None else history_bias
            if hour_bias is not None:
                adjusted_current_hour = round(float(forecast_current_hour) * float(hour_bias), 5)

        adjusted_next_hour = None
        if forecast_next_hour is not None:
            hour_bias = hourly_bias_by_hour[next_hour_idx] if hourly_bias_by_hour[next_hour_idx] is not None else history_bias
            if hour_bias is not None:
                adjusted_next_hour = round(float(forecast_next_hour) * float(hour_bias), 5)

        raw_today_profile = self._build_profile_from_total(forecast_remaining, hourly_share_by_hour, start_hour=current_hour_idx, end_hour=23)
        adjusted_today_profile = self._apply_hourly_bias(raw_today_profile, hourly_bias_by_hour, history_bias)
        for hour, value in today_actual_hourly.items():
            if 0 <= hour <= 23:
                adjusted_today_profile[hour] = round(float(value), 5)

        raw_tomorrow_profile = self._build_profile_from_total(forecast_tomorrow_total, hourly_share_by_hour)
        adjusted_tomorrow_profile = self._apply_hourly_bias(raw_tomorrow_profile, hourly_bias_by_hour, history_bias)

        adjusted_tomorrow_total = None
        if any(value is not None for value in adjusted_tomorrow_profile):
            adjusted_tomorrow_total = round(sum(value or 0.0 for value in adjusted_tomorrow_profile), 5)
        elif forecast_tomorrow_total is not None and history_bias is not None:
            adjusted_tomorrow_total = round(float(forecast_tomorrow_total) * float(history_bias), 5)

        projection_gap_tomorrow = None
        if adjusted_tomorrow_total is not None and forecast_tomorrow_total is not None:
            projection_gap_tomorrow = round(float(adjusted_tomorrow_total) - float(forecast_tomorrow_total), 5)

        anchor_watts = {
            1: res["status"].get("power_next_hour"),
            12: res["status"].get("power_next_12hours"),
            24: res["status"].get("power_next_24hours"),
        }
        next_24hours_profile_w = self._hourly_profile_to_horizon_watts(
            now_local,
            raw_today_profile,
            raw_tomorrow_profile,
            horizon_hours=24,
            anchor_watts=anchor_watts,
        )
        next_12hours_profile_w = next_24hours_profile_w[:12]

        res["status"]["power_production_next_hour_w"] = res["status"].get("power_next_hour")
        res["status"]["power_production_next_12hours_w"] = res["status"].get("power_next_12hours")
        res["status"]["power_production_next_24hours_w"] = res["status"].get("power_next_24hours")
        res["status"]["power_production_next_12hours_w_by_hour"] = next_12hours_profile_w
        res["status"]["power_production_next_24hours_w_by_hour"] = next_24hours_profile_w

        res["comparison"].update(
            {
                "forecast_so_far_kwh": round(float(forecast_so_far), 5) if forecast_so_far is not None else None,
                "delta_so_far_kwh": delta_so_far,
                "power_delta_w": power_delta,
                "live_ratio": live_ratio,
                "historical_bias_ratio": history_bias,
                "remaining_hourly_bias_ratio": remaining_hourly_bias,
                "effective_bias_ratio": effective_bias,
                "adjusted_projection_today_kwh": adjusted_projection,
                "projection_delta_to_forecast_kwh": projection_gap,
                "adjusted_projection_tomorrow_kwh": adjusted_tomorrow_total,
                "projection_delta_to_forecast_tomorrow_kwh": projection_gap_tomorrow,
                "adjusted_current_hour_kwh": adjusted_current_hour,
                "adjusted_next_hour_kwh": adjusted_next_hour,
                "adjusted_today_hourly_profile_kwh_by_hour": adjusted_today_profile,
                "adjusted_tomorrow_hourly_profile_kwh_by_hour": adjusted_tomorrow_profile,
                "future_profile_source": (
                    "live_anchors_plus_historical_shape"
                    if any(value is not None for value in anchor_watts.values())
                    else "historical_fallback"
                ),
            }
        )
        history_summary["profile_sources_available"] = {
            "historical_hourly": bool(history_hourly.get("days_tracked")),
            "live_next_hour": res["status"].get("power_next_hour") is not None,
            "live_next_12hours": res["status"].get("power_next_12hours") is not None,
            "live_next_24hours": res["status"].get("power_next_24hours") is not None,
        }
        res["history"] = history_summary

        today_forecast_hourly = _empty_hourly_list()
        if forecast_current_hour is not None:
            today_forecast_hourly[current_hour_idx] = round(float(forecast_current_hour), 5)
        if forecast_next_hour is not None:
            today_forecast_hourly[next_hour_idx] = round(float(forecast_next_hour), 5)

        history[date_str] = {
            "updated_at": now_local.isoformat(),
            "actual_total_kwh": actual_total,
            "actual_power_now_w": actual_power_now,
            "forecast_power_now_w": forecast_power_now,
            "forecast_so_far_kwh": forecast_so_far,
            "forecast_remaining_kwh": forecast_remaining,
            "forecast_total_kwh": forecast_total,
            "forecast_total_source": "production_today_live",
            "forecast_hourly_kwh_by_hour": today_forecast_hourly,
            "actual_hourly_kwh_by_hour": _serialize_hourly_map(today_actual_hourly),
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
