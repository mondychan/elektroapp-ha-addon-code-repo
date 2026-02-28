from fastapi import APIRouter, Body, Query

import app_service as svc
from config_models import AppConfigModel


router = APIRouter(prefix="/api")


@router.get("/config", response_model=AppConfigModel)
def get_config():
    return AppConfigModel.model_validate(svc.get_config())


@router.post("/config")
def save_config(new_config: AppConfigModel = Body(...)):
    return svc.save_config(new_config.model_dump(mode="python"))


@router.get("/fees-history")
def get_fees_history():
    return svc.get_fees_history()


@router.put("/fees-history")
def update_fees_history(payload: dict = Body(...)):
    return svc.update_fees_history(payload)


@router.get("/cache-status")
def get_cache_status():
    return svc.get_cache_status()


@router.get("/version")
def get_version():
    return svc.get_version()


@router.get("/prices")
def get_prices(date: str = Query(default=None)):
    return svc.get_prices(date=date)


@router.post("/prices/refresh")
def refresh_prices(payload: dict = Body(default=None)):
    return svc.refresh_prices(payload=payload)


@router.get("/consumption")
def get_consumption(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    return svc.get_consumption(date=date, start=start, end=end)


@router.get("/costs")
def get_costs(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    return svc.get_costs(date=date, start=start, end=end)


@router.get("/export")
def get_export(
    date: str = Query(default=None),
    start: str = Query(default=None),
    end: str = Query(default=None),
):
    return svc.get_export(date=date, start=start, end=end)


@router.get("/battery")
def get_battery(date: str = Query(default=None)):
    return svc.get_battery(date=date)


@router.get("/energy-balance")
def get_energy_balance(
    period: str = Query(default="week"),
    anchor: str = Query(default=None),
):
    return svc.get_energy_balance(period=period, anchor=anchor)


@router.get("/history-heatmap")
def get_history_heatmap(
    month: str = Query(default=None),
    metric: str = Query(default="buy"),
):
    return svc.get_history_heatmap(month=month, metric=metric)


@router.get("/schedule")
def get_schedule(
    duration: int = Query(default=120, ge=1, le=360),
    count: int = Query(default=3, ge=1, le=3),
    duration_minutes: int = Query(default=None, ge=1, le=360, deprecated=True),
    date: str = Query(default=None, deprecated=True),
):
    # Backward compatibility for older clients that still send duration_minutes.
    effective_duration = duration_minutes if isinstance(duration_minutes, int) else duration
    return svc.get_schedule(duration=effective_duration, count=count)


@router.get("/daily-summary")
def get_daily_summary(month: str = Query(...)):
    return svc.get_daily_summary(month=month)


@router.get("/billing-month")
def get_billing_month(month: str = Query(...)):
    return svc.get_billing_month(month=month)


@router.get("/billing-year")
def get_billing_year(year: int = Query(..., ge=2000, le=2100)):
    return svc.get_billing_year(year=year)
