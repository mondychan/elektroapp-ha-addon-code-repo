from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from battery import get_slot_index_for_dt
from services.battery_projection import build_hybrid_battery_projection


def test_hybrid_battery_projection_uses_near_term_state_and_keeps_later_milestones():
    tzinfo = ZoneInfo("Europe/Prague")
    now_local = datetime(2026, 4, 5, 11, 50, tzinfo=tzinfo)

    load_profile = {}
    pv_profile = {}
    probe_time = now_local

    while probe_time <= now_local.replace(hour=23, minute=59):
        slot = get_slot_index_for_dt(probe_time)
        if probe_time < now_local.replace(hour=14, minute=30):
            pv_profile[slot] = 3200.0
            load_profile[slot] = 400.0
        elif probe_time < now_local.replace(hour=18, minute=0):
            pv_profile[slot] = 900.0
            load_profile[slot] = 800.0
        else:
            pv_profile[slot] = 0.0
            load_profile[slot] = 2600.0
        probe_time = probe_time.replace(second=0, microsecond=0)
        probe_time = probe_time + timedelta(minutes=15)

    projection = build_hybrid_battery_projection(
        now_local=now_local,
        soc_percent=52.0,
        avg_power_w=1800.0,
        battery_cfg={
            "usable_capacity_kwh": 10.0,
            "reserve_soc_percent": 10.0,
            "charge_efficiency": 1.0,
            "discharge_efficiency": 1.0,
            "min_power_threshold_w": 100.0,
        },
        tzinfo=tzinfo,
        interval_minutes=15,
        current_energy={
            "house_load_w": 400.0,
            "pv_power_total_w": 3200.0,
        },
        forecast_payload={
            "power_now_w": 3200.0,
            "energy_next_hour_kwh": 3.2,
            "energy_production_today_remaining_kwh": 14.0,
        },
        load_profile=load_profile,
        pv_profile=pv_profile,
    )

    assert projection is not None
    assert projection["state"] == "charging"
    assert projection["end_state"] == "discharging"
    assert projection["eta_to_full_at"] is not None
    assert projection["eta_to_reserve_after_full_at"] is not None
    assert projection["eta_to_reserve_after_full_minutes"] > projection["eta_to_full_minutes"]
    assert projection["peak_soc_percent"] >= 99.0
