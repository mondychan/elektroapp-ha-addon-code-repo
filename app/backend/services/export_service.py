from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from fastapi import HTTPException


class ExportService:
    def __init__(
        self,
        *,
        get_export_points: Callable[..., dict[str, Any]],
        build_price_map_for_date: Callable[..., tuple[dict[str, dict[str, float]], dict[str, dict[str, float]]]],
        get_fee_snapshot_for_date: Callable[..., dict[str, Any]],
        calculate_sell_coefficient: Callable[..., float] | None = None,
        get_sell_coefficient_kwh: Callable[..., float] | None = None,
    ):
        self._get_export_points = get_export_points
        self._build_price_map_for_date = build_price_map_for_date
        self._get_fee_snapshot_for_date = get_fee_snapshot_for_date
        self._calculate_sell_coefficient = calculate_sell_coefficient or get_sell_coefficient_kwh
        if self._calculate_sell_coefficient is None:
             raise TypeError("ExportService missing calculate_sell_coefficient or get_sell_coefficient_kwh")

    @staticmethod
    def _slot_key_from_iso(value: str | None) -> str | None:
        if not isinstance(value, str) or len(value) < 16 or value[10] != "T":
            return None
        return f"{value[:10]} {value[11:16]}"

    def get_export(
        self,
        *,
        date: str | None,
        start: str | None,
        end: str | None,
        cfg: dict[str, Any],
        tzinfo,
    ) -> dict[str, Any]:
        export = self._get_export_points(cfg, date, start, end)
        tzinfo = export.get("tzinfo") or tzinfo

        if not export.get("has_series", False):
            if date:
                try:
                    date_obj = datetime.strptime(date, "%Y-%m-%d").date()
                    if date_obj <= datetime.now(tzinfo).date():
                        raise HTTPException(
                            status_code=500,
                            detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj export entity_id.",
                        )
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")
            else:
                range_end = datetime.fromisoformat(export["range"]["end"].replace("Z", "+00:00"))
                if range_end <= datetime.now(timezone.utc):
                    raise HTTPException(
                        status_code=500,
                        detail="Nepodarilo se nacist data z InfluxDB. Zkontroluj export entity_id.",
                    )

        target_date = date
        if not target_date:
            first_point = (export.get("points") or [{}])[0]
            first_time = first_point.get("time")
            if isinstance(first_time, str) and len(first_time) >= 10:
                target_date = first_time[:10]
            else:
                start_dt = datetime.fromisoformat(export["range"]["start"].replace("Z", "+00:00"))
                target_date = start_dt.astimezone(tzinfo).strftime("%Y-%m-%d")
        price_map, price_map_utc = self._build_price_map_for_date(cfg, target_date, tzinfo)

        coef_by_date: dict[str, float] = {}
        points = []
        total_kwh = 0.0
        total_sell = 0.0
        for entry in export["points"]:
            kwh = entry["kwh"]
            local_key = self._slot_key_from_iso(entry.get("time"))
            price = price_map.get(local_key) if local_key else None
            if price is None:
                utc_key = self._slot_key_from_iso(entry.get("time_utc"))
                price = price_map_utc.get(utc_key) if utc_key else None
            spot_price = price["spot"] if price else None
            date_key = (entry.get("time") or "")[:10] if isinstance(entry.get("time"), str) else None
            if not date_key:
                date_key = target_date
            coef_kwh = coef_by_date.get(date_key)
            if coef_kwh is None:
                fee_snapshot = self._get_fee_snapshot_for_date(cfg, date_key, tzinfo)
                coef_kwh = self._calculate_sell_coefficient(cfg, fee_snapshot)
                coef_by_date[date_key] = coef_kwh
            sell_price = spot_price - coef_kwh if spot_price is not None else None
            sell = None
            if kwh is not None and sell_price is not None:
                sell = round(kwh * sell_price, 5)
                total_kwh += kwh
                total_sell += sell

            points.append(
                {
                    "time": entry["time"],
                    "time_utc": entry["time_utc"],
                    "kwh": kwh,
                    "spot_price": spot_price,
                    "sell_price": round(sell_price, 5) if sell_price is not None else None,
                    "sell": sell,
                }
            )

        return {
            "range": export["range"],
            "interval": export["interval"],
            "entity_id": export["entity_id"],
            "summary": {
                "export_kwh_total": round(total_kwh, 5),
                "sell_total": round(total_sell, 5),
            },
            "points": points,
            "from_cache": export.get("from_cache", False),
            "cache_fallback": export.get("cache_fallback", False),
        }
