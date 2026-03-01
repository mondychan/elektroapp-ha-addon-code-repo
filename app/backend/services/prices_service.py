from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Callable

from fastapi import HTTPException


class PricesService:
    def __init__(
        self,
        *,
        get_prices_for_date: Callable[..., list[dict[str, Any]]],
        get_price_provider: Callable[[dict[str, Any]], str],
        clear_prices_cache_for_date: Callable[..., None],
    ):
        self._get_prices_for_date = get_prices_for_date
        self._get_price_provider = get_price_provider
        self._clear_prices_cache_for_date = clear_prices_cache_for_date

    def get_prices(self, *, date: str | None, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        if date:
            return {"prices": self._get_prices_for_date(cfg, date, tzinfo)}

        final_list: list[dict[str, Any]] = []
        now = datetime.now(tzinfo)
        today_str = now.strftime("%Y-%m-%d")
        final_list.extend(self._get_prices_for_date(cfg, today_str, tzinfo, include_neighbor_live=True))
        tomorrow_str = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        final_list.extend(self._get_prices_for_date(cfg, tomorrow_str, tzinfo))
        return {"prices": final_list}

    def refresh_prices(self, *, payload: dict[str, Any] | None, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        payload = payload or {}
        provider = self._get_price_provider(cfg)

        dates_to_refresh: list[str] = []
        requested_date = payload.get("date")
        if requested_date:
            try:
                datetime.strptime(str(requested_date), "%Y-%m-%d")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.") from exc
            dates_to_refresh.append(str(requested_date))
        else:
            today_str = datetime.now(tzinfo).strftime("%Y-%m-%d")
            tomorrow_str = (datetime.now(tzinfo) + timedelta(days=1)).strftime("%Y-%m-%d")
            dates_to_refresh.extend([today_str, tomorrow_str])

        refreshed = []
        for date_str in dates_to_refresh:
            self._clear_prices_cache_for_date(date_str, remove_files=False)
            entries = self._get_prices_for_date(cfg, date_str, tzinfo, force_refresh=True)
            refreshed.append(
                {
                    "date": date_str,
                    "count": len(entries),
                    "has_data": bool(entries),
                }
            )

        return {
            "status": "ok",
            "provider": provider,
            "refreshed": refreshed,
        }
