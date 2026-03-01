from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable


class ScheduleService:
    def __init__(self, *, get_prices_for_date: Callable[..., list[dict[str, Any]]]):
        self._get_prices_for_date = get_prices_for_date

    def get_schedule(self, *, duration: int, count: int, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        now = datetime.now(tzinfo)
        today = now.date()
        tomorrow = today + timedelta(days=1)

        duration = max(1, min(360, duration))

        def next_slot(dt):
            minute = (dt.minute // 15 + (1 if dt.minute % 15 else 0)) * 15
            if minute == 60:
                return dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            return dt.replace(minute=minute, second=0, microsecond=0)

        min_start = next_slot(now)
        slots = int((duration + 14) // 15)
        candidates = []

        for date_obj in (today, tomorrow):
            date_str = date_obj.strftime("%Y-%m-%d")
            entries = self._get_prices_for_date(cfg, date_str, tzinfo)
            if not entries:
                continue
            entries_sorted = sorted(entries, key=lambda x: x["time"])
            if len(entries_sorted) < slots:
                continue
            for i in range(0, len(entries_sorted) - slots + 1):
                window = entries_sorted[i : i + slots]
                window_start = datetime.strptime(window[0]["time"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
                if date_obj == today and window_start < min_start:
                    continue
                avg_price = sum(p["final"] for p in window) / slots
                energy_kwh = duration / 60.0
                total_cost = avg_price * energy_kwh
                end_dt = window_start + timedelta(minutes=duration)
                candidates.append(
                    {
                        "start": window[0]["time"],
                        "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                        "avg_price": round(avg_price, 5),
                        "energy_kwh": round(energy_kwh, 3),
                        "total_cost": round(total_cost, 5),
                    }
                )

        if not candidates:
            return {"duration": duration, "recommendations": [], "note": "Data nejsou k dispozici."}

        candidates.sort(key=lambda x: (x["avg_price"], x["start"]))
        results = []
        for item in candidates:
            start_dt = datetime.strptime(item["start"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
            if all(
                abs(
                    (
                        start_dt
                        - datetime.strptime(r["start"], "%Y-%m-%d %H:%M").replace(tzinfo=tzinfo)
                    ).total_seconds()
                )
                >= duration * 60
                for r in results
            ):
                results.append(item)
            if len(results) >= count:
                break

        return {
            "duration": duration,
            "recommendations": results,
            "note": None,
        }
