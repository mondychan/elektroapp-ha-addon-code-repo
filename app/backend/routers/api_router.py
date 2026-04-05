from fastapi import APIRouter, Body, Depends, Query

import app_service as svc
from config_models import AppConfigModel
from dependencies import RequestContext, get_request_context
from query_models import DateRangeQuery, EnergyBalanceQuery, HeatmapQuery, MonthQuery, OptionalDateQuery


router = APIRouter(prefix="/api")


@router.get("/config", response_model=AppConfigModel)
def get_config():
    return AppConfigModel.model_validate(svc.get_config())


@router.post("/config")
def save_config(new_config: AppConfigModel = Body(...)):
    return svc.save_config(new_config.model_dump(mode="python"))


@router.get("/fees-history")
def get_fees_history(ctx: RequestContext = Depends(get_request_context)):
    return svc.get_fees_history(cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.put("/fees-history")
def update_fees_history(payload: dict = Body(...), ctx: RequestContext = Depends(get_request_context)):
    return svc.update_fees_history(payload, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/cache-status")
def get_cache_status():
    return svc.get_cache_status()


@router.get("/version")
def get_version():
    return svc.get_version()


@router.get("/prices")
def get_prices(params: OptionalDateQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_prices(date=params.date, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.post("/prices/refresh")
def refresh_prices(payload: dict = Body(default=None), ctx: RequestContext = Depends(get_request_context)):
    return svc.refresh_prices(payload=payload, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/consumption")
def get_consumption(
    params: DateRangeQuery = Depends(),
    ctx: RequestContext = Depends(get_request_context),
):
    return svc.get_consumption(date=params.date, start=params.start, end=params.end, cfg=ctx.config)


@router.get("/costs")
def get_costs(
    params: DateRangeQuery = Depends(),
    ctx: RequestContext = Depends(get_request_context),
):
    return svc.get_costs(
        date=params.date,
        start=params.start,
        end=params.end,
        cfg=ctx.config,
        tzinfo=ctx.tzinfo,
    )


@router.get("/export")
def get_export(
    params: DateRangeQuery = Depends(),
    ctx: RequestContext = Depends(get_request_context),
):
    return svc.get_export(
        date=params.date,
        start=params.start,
        end=params.end,
        cfg=ctx.config,
        tzinfo=ctx.tzinfo,
    )


@router.get("/battery")
def get_battery(params: OptionalDateQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_battery(date=params.date, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/energy-balance")
def get_energy_balance(
    params: EnergyBalanceQuery = Depends(),
    ctx: RequestContext = Depends(get_request_context),
):
    return svc.get_energy_balance(
        period=params.period,
        anchor=params.anchor,
        cfg=ctx.config,
        tzinfo=ctx.tzinfo,
    )


@router.get("/history-heatmap")
def get_history_heatmap(
    params: HeatmapQuery = Depends(),
    ctx: RequestContext = Depends(get_request_context),
):
    return svc.get_history_heatmap(
        month=params.month,
        metric=params.metric,
        cfg=ctx.config,
        tzinfo=ctx.tzinfo,
    )


@router.get("/schedule")
def get_schedule(
    duration: int = Query(default=120, ge=1, le=360),
    count: int = Query(default=3, ge=1, le=3),
    duration_minutes: int = Query(default=None, ge=1, le=360, deprecated=True),
    date: str = Query(default=None, deprecated=True),
    ctx: RequestContext = Depends(get_request_context),
):
    # Backward compatibility for older clients that still send duration_minutes.
    effective_duration = duration_minutes if isinstance(duration_minutes, int) else duration
    return svc.get_schedule(duration=effective_duration, count=count, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/daily-summary")
def get_daily_summary(params: MonthQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_daily_summary(month=params.month, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/billing-month")
def get_billing_month(params: MonthQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_billing_month(month=params.month, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/billing-year")
def get_billing_year(year: int = Query(..., ge=2000, le=2100), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_billing_year(year=year, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/alerts")
def get_alerts(ctx: RequestContext = Depends(get_request_context)):
    return svc.get_alerts(cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/comparison")
def get_comparison(params: OptionalDateQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return svc.get_comparison(date=params.date, cfg=ctx.config, tzinfo=ctx.tzinfo)


@router.get("/solar-forecast")
def get_solar_forecast(ctx: RequestContext = Depends(get_request_context)):
    return svc.get_solar_forecast(cfg=ctx.config)


@router.get("/dashboard-snapshot")
async def get_dashboard_snapshot(params: OptionalDateQuery = Depends(), ctx: RequestContext = Depends(get_request_context)):
    return await svc.get_dashboard_snapshot(date=params.date, cfg=ctx.config, tzinfo=ctx.tzinfo)
