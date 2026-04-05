import logging
from datetime import datetime, timedelta, timezone
from typing import Any, List, Dict, Optional
from api import to_rfc3339
from battery import build_slot_avg_profile, get_slot_index_for_dt
from pricing import _safe_float

logger = logging.getLogger("uvicorn.error")

def build_hybrid_battery_projection(
    now_local: datetime,
    soc_percent: Optional[float],
    avg_power_w: Optional[float],
    battery_cfg: Dict[str, Any],
    tzinfo,
    interval_minutes: int,
    current_energy: Dict[str, Any],
    forecast_payload: Dict[str, Any],
    load_profile: Dict[int, float],
    pv_profile: Dict[int, float],
) -> Optional[Dict[str, Any]]:
    usable_capacity_kwh = battery_cfg["usable_capacity_kwh"]
    reserve_soc = max(0.0, min(100.0, battery_cfg["reserve_soc_percent"]))
    charge_eff = max(0.01, min(1.0, battery_cfg["charge_efficiency"]))
    discharge_eff = max(0.01, min(1.0, battery_cfg["discharge_efficiency"]))
    min_power_threshold_w = battery_cfg["min_power_threshold_w"]

    if soc_percent is None or usable_capacity_kwh <= 0:
        return None

    step_minutes = max(5, min(60, int(interval_minutes or 15)))
    step_hours = step_minutes / 60.0
    current_energy_kwh = usable_capacity_kwh * max(0.0, min(100.0, soc_percent)) / 100.0
    target_full_kwh = usable_capacity_kwh
    target_reserve_kwh = usable_capacity_kwh * reserve_soc / 100.0
    end_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    current_load_w = current_energy.get("house_load_w") if isinstance(current_energy, dict) else None
    current_pv_w = current_energy.get("pv_power_total_w") if isinstance(current_energy, dict) else None
    power_now_w = forecast_payload.get("power_now_w") if isinstance(forecast_payload, dict) else None
    energy_next_hour_kwh = forecast_payload.get("energy_next_hour_kwh") if isinstance(forecast_payload, dict) else None
    remaining_today_kwh = (
        forecast_payload.get("energy_production_today_remaining_kwh") if isinstance(forecast_payload, dict) else None
    )

    if not load_profile and current_load_w is None:
        return None
    if not pv_profile and power_now_w is None and current_pv_w is None:
        return None

    future_steps = []
    probe_time = now_local
    max_points = int((24 * 60) / step_minutes) + 2
    for _ in range(max_points):
        if probe_time > end_of_day_local:
            break
        future_steps.append(probe_time)
        probe_time = probe_time + timedelta(minutes=step_minutes)
    if not future_steps:
        return None

    base_pv_power = []
    for dt_local in future_steps:
        slot = get_slot_index_for_dt(dt_local)
        base_pv_power.append(float(pv_profile.get(slot, current_pv_w or power_now_w or 0.0)))

    # Scale historical PV shape to today's remaining Forecast.Solar energy (if available).
    if remaining_today_kwh is not None and remaining_today_kwh >= 0:
        base_energy_kwh = sum(max(0.0, p) * step_hours / 1000.0 for p in base_pv_power)
        if base_energy_kwh > 0:
            scale = remaining_today_kwh / base_energy_kwh
            scale = max(0.0, min(scale, 5.0))
            base_pv_power = [p * scale for p in base_pv_power]

    # Anchor immediate forecast to current Forecast.Solar now power if available.
    if base_pv_power and power_now_w is not None:
        base_pv_power[0] = float(power_now_w)

    # Use Forecast.Solar next-hour energy as average power for the next hour slots.
    if energy_next_hour_kwh is not None and len(future_steps) > 1:
        next_hour_start = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
        next_hour_end = next_hour_start + timedelta(hours=1)
        next_hour_avg_w = max(0.0, float(energy_next_hour_kwh) * 1000.0)
        for idx, dt_local in enumerate(future_steps):
            if next_hour_start <= dt_local < next_hour_end:
                base_pv_power[idx] = next_hour_avg_w

    projection_points = []
    eta_to_full_minutes = None
    eta_to_reserve_minutes = None
    eta_to_full_at = None
    eta_to_reserve_at = None
    state = "idle"
    sim_energy_kwh = current_energy_kwh
    last_pred_battery_w = None

    for idx, dt_local in enumerate(future_steps):
        slot = get_slot_index_for_dt(dt_local)
        predicted_load_w = float(load_profile.get(slot, current_load_w or 0.0))
        predicted_pv_w = max(0.0, float(base_pv_power[idx] if idx < len(base_pv_power) else 0.0))
        predicted_battery_w = predicted_pv_w - predicted_load_w

        # Blend with measured battery trend to reduce jumps at "now".
        if avg_power_w is not None:
            blend_weight = 0.55 if idx == 0 else (0.35 if idx < 4 else 0.15)
            predicted_battery_w = (predicted_battery_w * (1 - blend_weight)) + (avg_power_w * blend_weight)

        last_pred_battery_w = predicted_battery_w
        if predicted_battery_w > min_power_threshold_w:
            state = "charging"
        elif predicted_battery_w < -min_power_threshold_w:
            state = "discharging"
        else:
            state = "idle"

        projection_points.append(
            {
                "time": dt_local.isoformat(),
                "time_utc": to_rfc3339(dt_local.astimezone(timezone.utc)),
                "soc_percent": round(max(0.0, min(100.0, (sim_energy_kwh / usable_capacity_kwh) * 100.0)), 3),
                "predicted_load_w": round(predicted_load_w, 3),
                "predicted_pv_w": round(predicted_pv_w, 3),
                "predicted_battery_w": round(predicted_battery_w, 3),
            }
        )

        if idx == len(future_steps) - 1:
            break

        delta_kwh = (predicted_battery_w / 1000.0) * step_hours
        if delta_kwh >= 0:
            delta_kwh *= charge_eff
        else:
            delta_kwh /= discharge_eff
        next_energy_kwh = min(max(0.0, sim_energy_kwh + delta_kwh), usable_capacity_kwh)

        if eta_to_full_minutes is None and sim_energy_kwh < target_full_kwh <= next_energy_kwh:
            eta_to_full_minutes = round((dt_local + timedelta(minutes=step_minutes) - now_local).total_seconds() / 60)
            eta_to_full_at = (now_local + timedelta(minutes=eta_to_full_minutes)).isoformat()
        if eta_to_reserve_minutes is None and sim_energy_kwh > target_reserve_kwh >= next_energy_kwh:
            eta_to_reserve_minutes = round((dt_local + timedelta(minutes=step_minutes) - now_local).total_seconds() / 60)
            eta_to_reserve_at = (now_local + timedelta(minutes=eta_to_reserve_minutes)).isoformat()

        sim_energy_kwh = next_energy_kwh

    confidence = "medium" if (remaining_today_kwh is not None and load_profile and pv_profile) else "low"
    if last_pred_battery_w is not None:
        if abs(last_pred_battery_w) < min_power_threshold_w:
            state = "idle"
        elif last_pred_battery_w > 0:
            state = "charging"
        else:
            state = "discharging"

    return {
        "method": "hybrid_forecast_load_profile",
        "confidence": confidence,
        "state": state,
        "eta_to_full_minutes": eta_to_full_minutes,
        "eta_to_reserve_minutes": eta_to_reserve_minutes,
        "eta_to_full_at": eta_to_full_at,
        "eta_to_reserve_at": eta_to_reserve_at,
        "step_minutes": step_minutes,
        "points": projection_points,
        "inputs": {
            "uses_load_profile": bool(load_profile),
            "uses_pv_profile": bool(pv_profile),
            "uses_forecast_remaining": remaining_today_kwh is not None,
            "uses_forecast_power_now": power_now_w is not None,
            "uses_forecast_next_hour": energy_next_hour_kwh is not None,
        },
    }

def build_battery_projection(
    now_local: datetime,
    soc_percent: Optional[float],
    avg_power_w: Optional[float],
    battery_cfg: Dict[str, Any],
    tzinfo,
    parse_influx_interval_to_minutes_fn
) -> Dict[str, Any]:
    usable_capacity_kwh = battery_cfg["usable_capacity_kwh"]
    reserve_soc = max(0.0, min(100.0, battery_cfg["reserve_soc_percent"]))
    min_power_threshold_w = battery_cfg["min_power_threshold_w"]
    charge_eff = max(0.01, min(1.0, battery_cfg["charge_efficiency"]))
    discharge_eff = max(0.01, min(1.0, battery_cfg["discharge_efficiency"]))

    if soc_percent is None or usable_capacity_kwh <= 0 or avg_power_w is None:
        return {
            "method": "trend",
            "confidence": "low",
            "state": "unknown",
            "eta_to_full_minutes": None,
            "eta_to_reserve_minutes": None,
            "eta_to_full_at": None,
            "eta_to_reserve_at": None,
            "points": [],
        }

    if abs(avg_power_w) < min_power_threshold_w:
        return {
            "method": "trend",
            "confidence": "low",
            "state": "idle",
            "eta_to_full_minutes": None,
            "eta_to_reserve_minutes": None,
            "eta_to_full_at": None,
            "eta_to_reserve_at": None,
            "points": [],
        }

    current_energy_kwh = usable_capacity_kwh * max(0.0, min(100.0, soc_percent)) / 100.0
    target_full_kwh = usable_capacity_kwh
    target_reserve_kwh = usable_capacity_kwh * reserve_soc / 100.0

    if avg_power_w > 0:
        delta_kwh_per_hour = (avg_power_w / 1000.0) * charge_eff
        state = "charging"
    else:
        delta_kwh_per_hour = (avg_power_w / 1000.0) / discharge_eff
        state = "discharging"

    eta_to_full_minutes = None
    eta_to_reserve_minutes = None
    eta_to_full_at = None
    eta_to_reserve_at = None

    if delta_kwh_per_hour > 0 and current_energy_kwh < target_full_kwh:
        eta_hours = (target_full_kwh - current_energy_kwh) / delta_kwh_per_hour if delta_kwh_per_hour else None
        if eta_hours is not None and eta_hours >= 0:
            eta_to_full_minutes = round(eta_hours * 60)
            eta_to_full_at = (now_local + timedelta(minutes=eta_to_full_minutes)).isoformat()
    if delta_kwh_per_hour < 0 and current_energy_kwh > target_reserve_kwh:
        eta_hours = (current_energy_kwh - target_reserve_kwh) / abs(delta_kwh_per_hour) if delta_kwh_per_hour else None
        if eta_hours is not None and eta_hours >= 0:
            eta_to_reserve_minutes = round(eta_hours * 60)
            eta_to_reserve_at = (now_local + timedelta(minutes=eta_to_reserve_minutes)).isoformat()

    end_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    step_minutes = max(5, min(60, parse_influx_interval_to_minutes_fn("15m")))
    projection_points = []
    proj_time = now_local
    proj_energy = current_energy_kwh
    step_delta = delta_kwh_per_hour * (step_minutes / 60.0)
    max_points = 96

    for _ in range(max_points):
        if proj_time > end_of_day_local:
            break
        projection_points.append(
            {
                "time": proj_time.isoformat(),
                "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                "soc_percent": round(max(0.0, min(100.0, (proj_energy / usable_capacity_kwh) * 100.0)), 3),
            }
        )
        next_time = proj_time + timedelta(minutes=step_minutes)
        if next_time > end_of_day_local:
            break
        proj_energy = min(max(0.0, proj_energy + step_delta), usable_capacity_kwh)
        proj_time = next_time
        if state == "charging" and proj_energy >= target_full_kwh:
            projection_points.append(
                {
                    "time": proj_time.isoformat(),
                    "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                    "soc_percent": 100.0,
                }
            )
            break
        if state == "discharging" and proj_energy <= target_reserve_kwh:
            projection_points.append(
                {
                    "time": proj_time.isoformat(),
                    "time_utc": to_rfc3339(proj_time.astimezone(timezone.utc)),
                    "soc_percent": round((target_reserve_kwh / usable_capacity_kwh) * 100.0, 3),
                }
            )
            break

    return {
        "method": "trend",
        "confidence": "low",
        "state": state,
        "eta_to_full_minutes": eta_to_full_minutes,
        "eta_to_reserve_minutes": eta_to_reserve_minutes,
        "eta_to_full_at": eta_to_full_at,
        "eta_to_reserve_at": eta_to_reserve_at,
        "step_minutes": step_minutes,
        "points": projection_points,
    }

def build_battery_history_points(soc_points: List[Dict[str, Any]], power_points: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_time = {}
    for point in soc_points or []:
        key = point["time"]
        row = by_time.setdefault(key, {"time": point["time"], "time_utc": point["time_utc"]})
        row["soc_percent"] = point.get("value")
    for point in power_points or []:
        key = point["time"]
        row = by_time.setdefault(key, {"time": point["time"], "time_utc": point["time_utc"]})
        row["battery_power_w"] = point.get("value")
    rows = list(by_time.values())
    rows.sort(key=lambda item: item.get("time_utc") or item.get("time") or "")
    return rows

def get_last_non_null_value(points: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    for point in reversed(points or []):
        value = point.get("value")
        if value is not None:
            return point
    return None

def iso_to_display_hhmm(iso_value: Any) -> Optional[str]:
    if not iso_value:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_value).replace("Z", "+00:00"))
    except ValueError:
        return str(iso_value)
    return dt.strftime("%H:%M")
