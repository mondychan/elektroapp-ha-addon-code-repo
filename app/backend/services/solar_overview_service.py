import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger("uvicorn.error")


def _default_get_local_tz(tz_name=None):
    try:
        return ZoneInfo(tz_name) if tz_name else datetime.now().astimezone().tzinfo
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return datetime.now().astimezone().tzinfo


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _interpolate_value(points, target_hour, tzinfo):
    if not points:
        return None
    for point in reversed(points):
        time_raw = point.get("time")
        if isinstance(time_raw, str):
            try:
                dt = datetime.fromisoformat(time_raw)
                if dt.tzinfo is None and tzinfo is not None:
                    dt = dt.replace(tzinfo=tzinfo)
                if dt.hour <= target_hour:
                    return _safe_float(point.get("value"))
            except ValueError:
                continue
    return None


def _coerce_watts(value, unit):
    numeric = _safe_float(value)
    if numeric is None:
        return None
    unit_lower = (unit or "").lower()
    if unit_lower == "kw":
        return numeric * 1000.0
    return numeric


class SolarOverviewService:
    def __init__(
        self,
        get_influx_cfg_fn,
        get_energy_entities_cfg_fn,
        get_forecast_solar_cfg_fn,
        get_solar_overview_cfg_fn,
        get_solar_forecast_fn,
        query_entity_series_fn,
        call_ha_service_fn,
        parse_influx_interval_to_minutes_fn=None,
        get_local_tz_fn=None,
        logger_instance=None,
    ):
        self.get_influx_cfg = get_influx_cfg_fn
        self.get_energy_entities_cfg = get_energy_entities_cfg_fn
        self.get_forecast_solar_cfg = get_forecast_solar_cfg_fn
        self.get_solar_overview_cfg = get_solar_overview_cfg_fn
        self.get_solar_forecast = get_solar_forecast_fn
        self.query_entity_series = query_entity_series_fn
        self.call_ha_service = call_ha_service_fn
        self.parse_influx_interval = parse_influx_interval_to_minutes_fn or (lambda *a, **kw: 15)
        self.get_local_tz = get_local_tz_fn or _default_get_local_tz
        self.log = logger_instance or logger

    def get_solar_overview(self, cfg: dict, date: Optional[str] = None) -> dict:
        so_cfg = self.get_solar_overview_cfg(cfg)
        if not so_cfg.get("enabled"):
            return {"enabled": False}

        tzinfo = self.get_local_tz(cfg.get("influxdb", {}).get("timezone"))
        now = datetime.now(tzinfo)
        if not date:
            date = now.strftime("%Y-%m-%d")

        try:
            target_date = datetime.strptime(date, "%Y-%m-%d").replace(tzinfo=tzinfo)
        except ValueError:
            return {"enabled": True, "error": f"Neplatné datum: {date}"}

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

        energy_data = None
        forecast = None
        weather = None
        energy_error = None
        forecast_error = None
        weather_error = None

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}

            def _submit(key, fn, *args):
                futures[executor.submit(fn, *args)] = key

            _submit("energy", self._fetch_energy_data, cfg, day_start, now, tzinfo)
            _submit("forecast", self._fetch_forecast, cfg)
            _submit("weather", self._fetch_weather, cfg, so_cfg, day_start, tzinfo)

            for future in as_completed(futures):
                key = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    self.log.warning("SolarOverview fetch %s failed: %s", key, exc)
                    if key == "energy":
                        energy_error = str(exc)
                    elif key == "forecast":
                        forecast_error = str(exc)
                    elif key == "weather":
                        weather_error = str(exc)
                    continue

                if key == "energy":
                    energy_data = result
                elif key == "forecast":
                    forecast = result
                elif key == "weather":
                    weather = result

        sources = {
            "weather": {
                "entity_id": so_cfg.get("weather_entity_id"),
                "available": weather is not None and not weather_error,
            },
            "energy": {"available": energy_data is not None and not energy_error},
            "forecast": {"available": forecast is not None and not forecast_error},
        }

        if energy_data is None and energy_error:
            return {
                "enabled": True,
                "date": date,
                "title": so_cfg.get("title"),
                "timezone": str(tzinfo),
                "error": energy_error,
                "sources": sources,
            }

        forecast_points = self._build_forecast_points(energy_data, forecast, weather, tzinfo, now)
        overview_points = self._build_overview_points(energy_data)
        totals = self._build_totals(energy_data, forecast)

        return {
            "enabled": True,
            "date": date,
            "title": so_cfg.get("title"),
            "timezone": str(tzinfo),
            "totals": totals,
            "forecast_chart": {
                "points": forecast_points,
                "now": now.isoformat(),
            },
            "overview_chart": {
                "points": overview_points,
            },
            "sources": sources,
        }

    def _fetch_energy_data(self, cfg, day_start, now, tzinfo):
        influx_cfg = self.get_influx_cfg(cfg)
        energy_cfg = self.get_energy_entities_cfg(cfg)
        start_utc = day_start.astimezone(ZoneInfo("UTC"))
        end_utc = min(now, day_start + timedelta(days=1)).astimezone(ZoneInfo("UTC"))

        entity_fields = {
            "pv_power_total_entity_id": "solar",
            "house_load_power_entity_id": "load",
            "grid_import_power_entity_id": "import",
            "grid_export_power_entity_id": "export",
        }

        result = {}
        interval = "15m"

        for cfg_key, label in entity_fields.items():
            entity_id = energy_cfg.get(cfg_key)
            if not entity_id:
                continue
            try:
                points = self.query_entity_series(
                    influx_cfg,
                    entity_id,
                    start_utc,
                    end_utc,
                    interval=interval,
                    tzinfo=tzinfo,
                    numeric=True,
                    measurement_candidates=["W", "kW"],
                )
                result[label] = points
            except Exception as exc:
                self.log.warning("SolarOverview energy query failed for %s: %s", entity_id, exc)

        return result if result else None

    def _fetch_forecast(self, cfg):
        try:
            return self.get_solar_forecast(cfg)
        except Exception:
            return None

    def _fetch_weather(self, cfg, so_cfg, target_date, tzinfo):
        weather_entity = so_cfg.get("weather_entity_id")
        if not weather_entity:
            return None
        try:
            response = self.call_ha_service(
                "weather",
                "get_forecasts",
                {"entity_id": weather_entity, "type": "hourly"},
                return_response=True,
            )
        except Exception as exc:
            self.log.warning("SolarOverview weather call failed with direct entity_id, retrying as target: %s", exc)
            try:
                response = self.call_ha_service(
                    "weather",
                    "get_forecasts",
                    {"target": {"entity_id": weather_entity}, "type": "hourly"},
                    return_response=True,
                )
            except Exception as exc2:
                self.log.warning("SolarOverview weather call failed: %s", exc2)
                return None

        if not isinstance(response, dict):
            return None

        forecast_list = None
        for key, val in response.items():
            if isinstance(val, dict) and "forecast" in val:
                forecast_list = val["forecast"]
                break

        if not isinstance(forecast_list, list) or not forecast_list:
            return None

        parsed = []
        for entry in forecast_list:
            if not isinstance(entry, dict):
                continue
            dt_raw = entry.get("datetime")
            if not dt_raw:
                continue
            try:
                dt = datetime.fromisoformat(str(dt_raw))
                if dt.tzinfo is None and tzinfo is not None:
                    dt = dt.replace(tzinfo=tzinfo)
            except ValueError:
                continue
            parsed.append({
                "time": dt,
                "condition": entry.get("condition"),
                "cloud_coverage": _safe_float(entry.get("cloud_coverage")),
                "temperature": _safe_float(entry.get("temperature")),
            })

        return parsed if parsed else None

    def _build_forecast_points(self, energy_data, forecast, weather, tzinfo, now):
        pv_points = (energy_data or {}).get("solar") or []

        hourly_forecast_w = self._extract_hourly_forecast_w(forecast)
        hour_count = len(hourly_forecast_w) if hourly_forecast_w else 24

        weather_by_hour = {}
        if weather:
            for w in weather:
                hour = w["time"].astimezone(tzinfo).hour
                weather_by_hour[hour] = w

        points = []
        for hour_idx in range(hour_count):
            hour_slot = datetime.fromtimestamp(0, tzinfo).replace(hour=hour_idx)
            time_iso = hour_slot.isoformat()

            generated_w = _interpolate_value(pv_points, hour_idx, tzinfo)
            if generated_w is not None:
                generated_w = round(generated_w)

            predicted_w = hourly_forecast_w[hour_idx] if hour_idx < len(hourly_forecast_w) else None
            if predicted_w is not None:
                predicted_w = round(predicted_w)

            w_info = weather_by_hour.get(hour_idx, {})
            cloud_pct = w_info.get("cloud_coverage") if w_info else None
            condition = w_info.get("condition") if w_info else None
            temp = w_info.get("temperature") if w_info else None

            points.append({
                "time": time_iso,
                "generated_w": generated_w,
                "predicted_w": predicted_w,
                "cloud_cover_percent": cloud_pct,
                "condition": condition,
                "temperature_c": round(temp, 1) if temp is not None else None,
            })

        return points

    def _extract_hourly_forecast_w(self, forecast):
        if not forecast:
            return [None] * 24

        hourly_kwh = None
        comparison = forecast.get("comparison")
        if isinstance(comparison, dict):
            hourly_kwh = comparison.get("adjusted_today_hourly_profile_kwh_by_hour")

        if not isinstance(hourly_kwh, list) or len(hourly_kwh) != 24:
            status = forecast.get("status")
            if isinstance(status, dict):
                hourly_kwh = status.get("power_production_next_24hours_w_by_hour")
                if isinstance(hourly_kwh, list) and len(hourly_kwh) == 24:
                    return [_safe_float(v) for v in hourly_kwh]

                partial = status.get("power_production_next_12hours_w_by_hour")
                if isinstance(partial, list) and partial:
                    result = [None] * 24
                    for i, v in enumerate(partial):
                        if i < 24:
                            result[i] = _safe_float(v)
                    return result

            return [None] * 24

        return [round(_safe_float(v) * 1000.0) if _safe_float(v) is not None else None for v in hourly_kwh]

    def _build_overview_points(self, energy_data):
        if not energy_data:
            return []

        pv = energy_data.get("solar") or []
        load = energy_data.get("load") or []
        imp = energy_data.get("import") or []
        exp = energy_data.get("export") or []

        all_times = set()
        for series in (pv, load, imp, exp):
            for p in series:
                t = p.get("time")
                if t:
                    all_times.add(t)

        sorted_times = sorted(all_times)

        by_time = {}
        for series, key in ((pv, "solar_pv_w"), (load, "load_w"), (imp, "grid_import_w"), (exp, "grid_export_w")):
            for p in series:
                t = p.get("time")
                if t:
                    if t not in by_time:
                        by_time[t] = {}
                    val = _safe_float(p.get("value"))
                    by_time[t][key] = round(val) if val is not None else None

        result = []
        for t in sorted_times:
            entry = by_time.get(t, {})
            result.append({
                "time": t,
                "solar_pv_w": entry.get("solar_pv_w"),
                "load_w": entry.get("load_w"),
                "grid_import_w": entry.get("grid_import_w"),
                "grid_export_w": entry.get("grid_export_w"),
            })

        return result

    def _build_totals(self, energy_data, forecast):
        generated_kwh = None
        if forecast:
            actual = forecast.get("actual")
            if isinstance(actual, dict):
                generated_kwh = _safe_float(actual.get("production_today_kwh"))
        if generated_kwh is None and energy_data:
            pv = energy_data.get("solar") or []
            generated_kwh = self._sum_series(pv)

        forecast_raw_today = None
        forecast_adj_today = None
        forecast_raw_tomorrow = None
        forecast_adj_tomorrow = None

        if forecast:
            comparison = forecast.get("comparison")
            if isinstance(comparison, dict):
                forecast_adj_today = _safe_float(comparison.get("adjusted_projection_today_kwh"))
                forecast_adj_tomorrow = _safe_float(comparison.get("adjusted_projection_tomorrow_kwh"))
            status = forecast.get("status")
            if isinstance(status, dict):
                forecast_raw_today = _safe_float(status.get("energy_production_today_kwh"))
                forecast_raw_tomorrow = _safe_float(status.get("energy_production_tomorrow_kwh"))

        remaining_raw = None
        remaining_adj = None
        if generated_kwh is not None:
            if forecast_raw_today is not None:
                remaining_raw = round(forecast_raw_today - generated_kwh, 3)
            if forecast_adj_today is not None:
                remaining_adj = round(forecast_adj_today - generated_kwh, 3)

        return {
            "generated_kwh": generated_kwh,
            "forecast_raw_today_kwh": forecast_raw_today,
            "forecast_adjusted_today_kwh": forecast_adj_today,
            "forecast_adjusted_tomorrow_kwh": forecast_adj_tomorrow,
        }

    def _sum_series(self, series, interval_minutes=15):
        total = 0.0
        for p in series:
            val = _safe_float(p.get("value"))
            if val is None:
                continue
            unit = (p.get("unit") or "").lower()
            if unit == "kw":
                val *= 1000.0
            total += val * (interval_minutes / 60.0) / 1000.0
        return round(total, 3) if total > 0 else None
