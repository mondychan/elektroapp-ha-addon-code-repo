from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException


class CostsService:
    def __init__(
        self,
        *,
        get_consumption_points: Callable[..., dict[str, Any]],
        build_price_map_for_date: Callable[..., tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]],
    ):
        self._get_consumption_points = get_consumption_points
        self._build_price_map_for_date = build_price_map_for_date

    @staticmethod
    def _slot_key_from_iso(value: str | None) -> str | None:
        if not isinstance(value, str) or len(value) < 16 or value[10] != "T":
            return None
        return f"{value[:10]} {value[11:16]}"

    def get_costs(
        self,
        *,
        date: str | None,
        start: str | None,
        end: str | None,
        cfg: dict[str, Any],
        tzinfo,
    ) -> dict[str, Any]:
        consumption = self._get_consumption_points(cfg, date, start, end)
        tzinfo = consumption.get("tzinfo") or tzinfo

        if not consumption.get("has_series", False):
            if date:
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                    if date_obj <= datetime.now(tzinfo).date():
                        raise HTTPException(
                            status_code=500,
                            detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
                        )
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
            else:
                range_end = datetime.fromisoformat(consumption["range"]["end"].replace("Z", "+00:00"))
                if range_end <= datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=500,
                        detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj entity_id.",
                    )

        target_date = date
        if not target_date:
            first_point = (consumption.get("points") or [{}])[0]
            first_time = first_point.get("time")
            if isinstance(first_time, str) and len(first_time) >= 10:
                target_date = first_time[:10]
            else:
                start_dt = datetime.fromisoformat(consumption["range"]["start"].replace("Z", "+00:00"))
                target_date = start_dt.astimezone(tzinfo).strftime("%Y-%m-%d")
        price_map, price_map_utc = self._build_price_map_for_date(cfg, target_date, tzinfo)

        points = []
        total_kwh = 0.0
        total_cost = 0.0
        for entry in consumption["points"]:
            kwh = entry["kwh"]
            local_key = self._slot_key_from_iso(entry.get("time"))
            price = price_map.get(local_key) if local_key else None
            if price is None:
                utc_key = self._slot_key_from_iso(entry.get("time_utc"))
                price = price_map_utc.get(utc_key) if utc_key else None
            final_price = price["final"] if price else None
            cost = None
            if kwh is not None and final_price is not None:
                cost = round(kwh * final_price, 5)
                total_kwh += kwh
                total_cost += cost

            points.append(
                {
                    "time": entry["time"],
                    "time_utc": entry["time_utc"],
                    "kwh": kwh,
                    "final_price": final_price,
                    "cost": cost,
                }
            )

        return {
            "range": consumption["range"],
            "interval": consumption["interval"],
            "entity_id": consumption["entity_id"],
            "summary": {
                "kwh_total": round(total_kwh, 5),
                "cost_total": round(total_cost, 5),
            },
            "points": points,
            "from_cache": consumption.get("from_cache", False),
            "cache_fallback": consumption.get("cache_fallback", False),
        }
