import logging
import requests
import re
import xml.etree.ElementTree as ET
from datetime import date as datetime_date, datetime, timedelta, timezone, time as datetime_time
from zoneinfo import ZoneInfo
from typing import Any, List, Dict, Tuple, Optional
from fastapi import HTTPException
from requests import RequestException

from api import get_local_tz, to_rfc3339
from pricing import (
    PRICE_PROVIDER_OTE,
    PRICE_PROVIDER_SPOT,
    _safe_float,
    calculate_final_price,
    get_price_provider,
    normalize_price_provider,
    parse_price_html,
    is_price_cache_provider_match,
)
from services.runtime_state import RuntimeState
from cache import should_use_daily_cache, is_today_date

logger = logging.getLogger("uvicorn.error")

OTE_PUBLIC_URL = "https://www.ote-cr.cz/services/PublicDataService"
OTE_PUBLIC_URL_HTTP = "http://www.ote-cr.cz/services/PublicDataService"
OTE_SOAP_ACTION_GET_DAM_PRICE_PERIOD_E = "http://www.ote-cr.cz/schema/service/public/GetDamPricePeriodE"
CNB_RATES_URL = "https://api.cnb.cz/cnbapi/exrates/daily"
OTE_PUBLIC_NS = "{http://www.ote-cr.cz/schema/service/public}"
SOAP_FAULT_NS = "{http://schemas.xmlsoap.org/soap/envelope/}"
PRAGUE_TZ = ZoneInfo("Europe/Prague")
OTE_FAILURE_RETRY_SECONDS = 600

RUNTIME_STATE = RuntimeState()

PRICES_CACHE = {}
PRICES_CACHE_PROVIDER = {}

def mark_ote_unavailable(reason):
    RUNTIME_STATE.mark_ote_unavailable(OTE_FAILURE_RETRY_SECONDS)
    logger.warning("OTE marked unavailable for %ss: %s", OTE_FAILURE_RETRY_SECONDS, reason)

def get_ote_backoff_remaining_seconds():
    return RUNTIME_STATE.get_ote_backoff_remaining_seconds()

def is_ote_unavailable():
    return RUNTIME_STATE.is_ote_unavailable()

def utc_now_iso_z():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

def build_entries_from_api(cfg, date_str, hours, fee_snapshot):
    entries = []
    for entry in hours:
        try:
            hour = int(entry.get("hour", 0))
            minute = int(entry.get("minute", 0))
            price_czk_mwh = float(entry.get("priceCZK"))
        except (TypeError, ValueError):
            logger.warning("Skipping invalid API price row for %s: %s", date_str, entry)
            continue
        spot_kwh = price_czk_mwh / 1000.0
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_entries_from_ote(
    cfg: dict[str, Any],
    date_str: str,
    items: List[Dict[str, Any]],
    fee_snapshot: Dict[str, Any],
    eur_to_czk_rate: float,
) -> List[Dict[str, Any]]:
    entries = []
    for item in items:
        hour = item["hour"]
        minute = item["minute"]
        spot_kwh = (item["price_eur_mwh"] * eur_to_czk_rate) / 1000.0
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_entries_from_spot_html(
    cfg: dict[str, Any],
    date_str: str,
    fee_snapshot: dict[str, Any],
) -> List[Dict[str, Any]]:
    logger.info("Fetching historical prices from HTML for %s", date_str)
    url = f"https://spotovaelektrina.cz/denni-ceny/{date_str}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    rows = parse_price_html(r.text)
    entries = []
    for time_str, price_czk in rows:
        hour, minute = map(int, time_str.split(":"))
        spot_kwh = price_czk / 1000
        final_price = calculate_final_price(spot_kwh, hour, cfg, fee_snapshot)
        entries.append(
            {
                "time": f"{date_str} {hour:02d}:{minute:02d}",
                "hour": hour,
                "minute": minute,
                "spot": round(spot_kwh, 5),
                "final": final_price,
            }
        )
    return entries

def build_ote_query(start_date: str, end_date: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pub="http://www.ote-cr.cz/schema/service/public">
  <soapenv:Header/>
  <soapenv:Body>
    <pub:GetDamPricePeriodE>
      <pub:StartDate>{start_date}</pub:StartDate>
      <pub:EndDate>{end_date}</pub:EndDate>
      <pub:PeriodResolution>PT15M</pub:PeriodResolution>
    </pub:GetDamPricePeriodE>
  </soapenv:Body>
</soapenv:Envelope>"""

def fetch_ote_prices_xml(start_date: datetime_date, end_date: datetime_date) -> str:
    query = build_ote_query(start_date.isoformat(), end_date.isoformat())
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "Accept": "text/xml",
        "SOAPAction": OTE_SOAP_ACTION_GET_DAM_PRICE_PERIOD_E,
    }
    last_exc = None
    for url in (OTE_PUBLIC_URL, OTE_PUBLIC_URL_HTTP):
        try:
            logger.info("Fetching OTE prices from %s for %s..%s", url, start_date, end_date)
            response = requests.post(url, data=query.encode("utf-8"), headers=headers, timeout=20)
            response.raise_for_status()
            return response.text
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning("OTE request failed via %s: %s", url, exc)

    if last_exc:
        raise last_exc
    raise HTTPException(status_code=502, detail="OTE request failed.")

def parse_ote_prices_xml(xml_text: str) -> Dict[str, List[Dict[str, Any]]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise HTTPException(status_code=502, detail="OTE response could not be parsed.") from exc

    fault = root.find(f".//{SOAP_FAULT_NS}Fault")
    if fault is not None:
        fault_string = fault.findtext("faultstring") or "Unknown OTE SOAP fault."
        raise HTTPException(status_code=502, detail=f"OTE request failed: {fault_string}")

    rows_by_date = {}
    for item in root.findall(f".//{OTE_PUBLIC_NS}Item"):
        date_text = item.findtext(f"{OTE_PUBLIC_NS}Date")
        period_index_text = item.findtext(f"{OTE_PUBLIC_NS}PeriodIndex")
        price_text = item.findtext(f"{OTE_PUBLIC_NS}Price")
        if not date_text or not period_index_text or not price_text:
            continue
        try:
            current_date = datetime.strptime(date_text, "%Y-%m-%d").date()
            period_index = int(period_index_text)
            if period_index < 1 or period_index > 100:
                continue
            price_eur_mwh = float(price_text)
        except ValueError:
            continue

        start_of_day_local = datetime.combine(current_date, datetime_time(0), tzinfo=PRAGUE_TZ)
        slot_utc = start_of_day_local.astimezone(timezone.utc) + timedelta(minutes=(period_index - 1) * 15)
        slot_local = slot_utc.astimezone(PRAGUE_TZ)
        slot_date = slot_local.strftime("%Y-%m-%d")

        rows_by_date.setdefault(slot_date, []).append(
            {
                "hour": slot_local.hour,
                "minute": slot_local.minute,
                "price_eur_mwh": price_eur_mwh,
            }
        )

    for date_str in rows_by_date:
        rows_by_date[date_str].sort(key=lambda item: (item["hour"], item["minute"]))
    return rows_by_date

def extract_eur_czk_from_cnb_payload(payload: Any) -> float | None:
    if not isinstance(payload, dict):
        return None
    rates = payload.get("rates")
    if not isinstance(rates, list):
        return None
    for rate in rates:
        if not isinstance(rate, dict):
            continue
        if str(rate.get("currencyCode", "")).upper() != "EUR":
            continue
        amount = _safe_float(rate.get("amount", 1))
        amount = amount if amount > 0 else 1.0
        value = _safe_float(rate.get("rate"))
        if value > 0:
            return value / amount
    return None

def get_eur_czk_rate_for_date(day: datetime_date) -> float:
    for offset in range(7):
        query_day = day - timedelta(days=offset)
        try:
            response = requests.get(CNB_RATES_URL, params={"date": query_day.isoformat()}, timeout=10)
        except requests.RequestException:
            continue
        if response.status_code >= 400:
            continue
        try:
            payload = response.json()
        except ValueError:
            continue
        eur_czk = extract_eur_czk_from_cnb_payload(payload)
        if eur_czk is not None:
            return eur_czk
    raise HTTPException(status_code=502, detail="CNB FX rate EUR/CZK is not available.")

def get_ote_entries_for_dates(
    cfg: dict[str, Any],
    dates: List[str],
    tzinfo,
    get_fee_snapshot_for_date_fn,
) -> Dict[str, List[Dict[str, Any]]]:
    if not dates:
        return {}
    date_objects = sorted({datetime.strptime(date_str, "%Y-%m-%d").date() for date_str in dates})
    xml_text = fetch_ote_prices_xml(date_objects[0], date_objects[-1])
    rows_by_date = parse_ote_prices_xml(xml_text)

    entries_by_date = {}
    eur_cache = {}
    for date_obj in date_objects:
        date_str = date_obj.strftime("%Y-%m-%d")
        if date_obj not in eur_cache:
            eur_cache[date_obj] = get_eur_czk_rate_for_date(date_obj)
        fee_snapshot = get_fee_snapshot_for_date_fn(cfg, date_str, tzinfo)
        entries_by_date[date_str] = build_entries_from_ote(
            cfg,
            date_str,
            rows_by_date.get(date_str, []),
            fee_snapshot,
            eur_cache[date_obj],
        )
    return entries_by_date

def get_spot_prices():
    url = "https://spotovaelektrina.cz/api/v1/price/get-prices-json-qh"
    logger.info("Fetching prices from API: %s", url)
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return r.json()

def apply_fee_snapshot(
    entries: List[Dict[str, Any]],
    cfg: dict[str, Any],
    fee_snapshot: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not entries:
        return []
    adjusted = []
    for entry in entries:
        hour = entry.get("hour", 0)
        spot = entry.get("spot", 0)
        final = calculate_final_price(spot, hour, cfg, fee_snapshot)
        adjusted.append({**entry, "final": final})
    return adjusted

def get_prices_for_date(
    cfg: dict[str, Any],
    date_str: str,
    tzinfo,
    force_refresh: bool = False,
    include_neighbor_live: bool = False,
    # Handlers injected from config_loader and cache_manager to prevent circular imports
    load_prices_cache_fn = None,
    save_prices_cache_fn = None,
    get_cached_price_provider_fn = None,
    get_fee_snapshot_for_date_fn = None,
) -> List[Dict[str, Any]]:
    provider = get_price_provider(cfg)
    effective_provider = provider
    fee_snapshot = get_fee_snapshot_for_date_fn(cfg, date_str, tzinfo)
    date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
    today = datetime.now(tzinfo).date()
    tomorrow = today + timedelta(days=1)
    is_live_date = date_obj in (today, tomorrow)

    if not force_refresh:
        cached = PRICES_CACHE.get(date_str)
        if cached:
            if not is_live_date or is_price_cache_provider_match(date_str, provider, get_cached_price_provider_fn):
                return apply_fee_snapshot(cached, cfg, fee_snapshot)
            cached_provider = get_cached_price_provider_fn(date_str)
            logger.info("Skipping in-memory cache for %s due to provider switch (%s -> %s)", date_str, cached_provider, provider)

        cached = load_prices_cache_fn(date_str)
        if cached:
            cached_provider = get_cached_price_provider_fn(date_str)
            if is_live_date and cached_provider != normalize_price_provider(provider):
                logger.info("Skipping file cache for %s due to provider switch (%s -> %s)", date_str, cached_provider, provider)
            else:
                PRICES_CACHE[date_str] = cached
                PRICES_CACHE_PROVIDER[date_str] = cached_provider
                logger.info("Prices cache hit for %s", date_str)
                return apply_fee_snapshot(cached, cfg, fee_snapshot)

    entries = []
    if is_live_date:
        today_str = today.strftime("%Y-%m-%d")
        tomorrow_str = tomorrow.strftime("%Y-%m-%d")
        requested_dates = []
        if date_obj == today:
            requested_dates.append(today_str)
            if include_neighbor_live:
                requested_dates.append(tomorrow_str)
        elif date_obj == tomorrow:
            requested_dates.append(tomorrow_str)

        needs_today = today_str in requested_dates
        needs_tomorrow = tomorrow_str in requested_dates
        today_entries = []
        tomorrow_entries = []
        today_provider = provider
        tomorrow_provider = provider

        if provider == PRICE_PROVIDER_OTE:
            if not force_refresh and is_ote_unavailable():
                logger.info("Skipping OTE live fetch for %s/%s due to cooldown (%ss left)", today_str, tomorrow_str, get_ote_backoff_remaining_seconds())
            else:
                try:
                    entries_by_date = get_ote_entries_for_dates(cfg, requested_dates, tzinfo, get_fee_snapshot_for_date_fn)
                    today_entries = entries_by_date.get(today_str, [])
                    tomorrow_entries = entries_by_date.get(tomorrow_str, [])
                except Exception as exc:
                    mark_ote_unavailable(exc)
                    logger.warning("OTE live prices fetch failed for %s/%s: %s", today_str, tomorrow_str, exc)

            if needs_today and not today_entries:
                cached_today = load_prices_cache_fn(today_str)
                if cached_today and is_price_cache_provider_match(today_str, PRICE_PROVIDER_OTE, get_cached_price_provider_fn):
                    today_entries, today_provider = cached_today, PRICE_PROVIDER_OTE
                    PRICES_CACHE[today_str], PRICES_CACHE_PROVIDER[today_str] = cached_today, PRICE_PROVIDER_OTE
            if needs_tomorrow and not tomorrow_entries:
                cached_tomorrow = load_prices_cache_fn(tomorrow_str)
                if cached_tomorrow and is_price_cache_provider_match(tomorrow_str, PRICE_PROVIDER_OTE, get_cached_price_provider_fn):
                    tomorrow_entries, tomorrow_provider = cached_tomorrow, PRICE_PROVIDER_OTE
                    PRICES_CACHE[tomorrow_str], PRICES_CACHE_PROVIDER[tomorrow_str] = cached_tomorrow, PRICE_PROVIDER_OTE
        else:
            try:
                data = get_spot_prices()
                today_snapshot = get_fee_snapshot_for_date_fn(cfg, today_str, tzinfo)
                tomorrow_snapshot = get_fee_snapshot_for_date_fn(cfg, tomorrow_str, tzinfo)
                today_entries = build_entries_from_api(cfg, today_str, data.get("hoursToday", []), today_snapshot)
                tomorrow_entries = build_entries_from_api(cfg, tomorrow_str, data.get("hoursTomorrow", []), tomorrow_snapshot)
            except Exception as exc:
                logger.warning("Spot live prices fetch failed for %s/%s: %s", today_str, tomorrow_str, exc)

            if needs_today and not today_entries:
                cached_today = load_prices_cache_fn(today_str)
                if cached_today and is_price_cache_provider_match(today_str, PRICE_PROVIDER_SPOT, get_cached_price_provider_fn):
                    today_entries, today_provider = cached_today, PRICE_PROVIDER_SPOT
                    PRICES_CACHE[today_str], PRICES_CACHE_PROVIDER[today_str] = cached_today, PRICE_PROVIDER_SPOT
            if needs_tomorrow and not tomorrow_entries:
                cached_tomorrow = load_prices_cache_fn(tomorrow_str)
                if cached_tomorrow and is_price_cache_provider_match(tomorrow_str, PRICE_PROVIDER_SPOT, get_cached_price_provider_fn):
                    tomorrow_entries, tomorrow_provider = cached_tomorrow, PRICE_PROVIDER_SPOT
                    PRICES_CACHE[tomorrow_str], PRICES_CACHE_PROVIDER[tomorrow_str] = cached_tomorrow, PRICE_PROVIDER_SPOT

        if needs_today and today_entries:
            PRICES_CACHE[today_str], PRICES_CACHE_PROVIDER[today_str] = today_entries, today_provider
            save_prices_cache_fn(today_str, today_entries, provider=today_provider)
        if needs_tomorrow and tomorrow_entries:
            PRICES_CACHE[tomorrow_str], PRICES_CACHE_PROVIDER[tomorrow_str] = tomorrow_entries, tomorrow_provider
            save_prices_cache_fn(tomorrow_str, tomorrow_entries, provider=tomorrow_provider)
        entries = today_entries if date_obj == today else tomorrow_entries
        effective_provider = today_provider if date_obj == today else tomorrow_provider
    else:
        if provider == PRICE_PROVIDER_OTE:
            if not force_refresh and is_ote_unavailable():
                logger.info("Skipping OTE historical fetch for %s due to cooldown", date_str)
            else:
                try:
                    entries_by_date = get_ote_entries_for_dates(cfg, [date_str], tzinfo, get_fee_snapshot_for_date_fn)
                    entries = entries_by_date.get(date_str, [])
                except Exception as exc:
                    mark_ote_unavailable(exc)
                    logger.warning("OTE historical prices fetch failed for %s: %s", date_str, exc)
        elif provider == PRICE_PROVIDER_SPOT:
            try:
                entries = build_entries_from_spot_html(cfg, date_str, fee_snapshot)
                effective_provider = PRICE_PROVIDER_SPOT
            except Exception as exc:
                logger.warning("Spot historical prices fetch failed for %s: %s", date_str, exc)

    if entries:
        PRICES_CACHE[date_str], PRICES_CACHE_PROVIDER[date_str] = entries, effective_provider
        save_prices_cache_fn(date_str, entries, provider=effective_provider)
    return apply_fee_snapshot(entries, cfg, fee_snapshot)

def build_price_map_for_date(cfg, date_str, tzinfo, get_prices_for_date_fn):
    try:
        entries = get_prices_for_date_fn(cfg=cfg, date=date_str, tzinfo=tzinfo)
    except TypeError as exc:
        message = str(exc)
        if "unexpected keyword argument" not in message and "positional argument" not in message:
            raise
        entries = get_prices_for_date_fn(cfg, date_str, tzinfo)
    price_map = {}
    price_map_utc = {}
    for entry in entries:
        time_local = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M")
        if time_local.tzinfo is None:
            time_local = time_local.replace(tzinfo=tzinfo)
        key_local = time_local.strftime("%Y-%m-%d %H:%M")
        key_utc = time_local.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M")
        price_map[key_local] = {"spot": entry["spot"], "final": entry["final"]}
        price_map_utc[key_utc] = {"spot": entry["spot"], "final": entry["final"]}
    return price_map, price_map_utc
