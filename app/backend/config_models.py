from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from pricing import DEFAULT_PRICE_PROVIDER, normalize_dph_percent, normalize_price_provider, parse_vt_periods


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DistribuceConfig(StrictModel):
    NT: float = Field(default=0.0)
    VT: float = Field(default=0.0)


class PoplatkyConfig(StrictModel):
    dan: float = Field(default=0.0)
    systemove_sluzby: float = Field(default=0.0)
    komodita_sluzba: float = Field(default=0.0)
    oze: float = Field(default=0.0, validation_alias=AliasChoices("oze", "poze"))
    distribuce: DistribuceConfig = Field(default_factory=DistribuceConfig)


class FixniDenniConfig(StrictModel):
    staly_plat: float = Field(default=0.0)


class FixniMesicniConfig(StrictModel):
    provoz_nesitove_infrastruktury: float = Field(default=0.0)
    jistic: float = Field(default=0.0)


class FixniConfig(StrictModel):
    denni: FixniDenniConfig = Field(default_factory=FixniDenniConfig)
    mesicni: FixniMesicniConfig = Field(default_factory=FixniMesicniConfig)


class TarifConfig(StrictModel):
    vt_periods: list[tuple[int, int]] = Field(default_factory=list)

    @field_validator("vt_periods", mode="before")
    @classmethod
    def parse_periods_from_string(cls, value):
        if value is None:
            return []
        if isinstance(value, str):
            return parse_vt_periods(value)
        return value

    @field_validator("vt_periods")
    @classmethod
    def validate_periods(cls, value):
        normalized: list[tuple[int, int]] = []
        for period in value:
            if not isinstance(period, (list, tuple)) or len(period) != 2:
                raise ValueError("Each VT period must be [start, end].")
            start = int(period[0])
            end = int(period[1])
            if start < 0 or start > 23 or end < 0 or end > 23:
                raise ValueError("VT period hours must be in range 0..23.")
            if start > end:
                raise ValueError("VT period start must be <= end.")
            normalized.append((start, end))
        return normalized


class InfluxDbConfig(StrictModel):
    host: str = Field(default="localhost", min_length=1)
    port: int = Field(default=8086, ge=1, le=65535)
    database: str = Field(default="homeassistant", min_length=1)
    retention_policy: str = Field(default="autogen")
    measurement: str = Field(default="kWh", min_length=1)
    field: str = Field(default="value", min_length=1)
    entity_id: str = Field(default="", min_length=1)
    export_entity_id: str | None = None
    username: str | None = None
    password: str | None = None
    timezone: str = Field(default="Europe/Prague", min_length=1)
    interval: str = Field(default="15m", pattern=r"^\d+[smhd]$")


class ProdejConfig(StrictModel):
    koeficient_snizeni_ceny: float = Field(default=0.0)


class BatteryConfig(StrictModel):
    enabled: bool = False
    soc_entity_id: str | None = None
    power_entity_id: str | None = None
    input_energy_today_entity_id: str | None = None
    output_energy_today_entity_id: str | None = None
    usable_capacity_kwh: float = Field(default=0.0, ge=0.0)
    reserve_soc_percent: float = Field(default=15.0, ge=0.0, le=100.0)
    eta_smoothing_minutes: int = Field(default=15, ge=1, le=1440)
    min_power_threshold_w: float = Field(default=150.0, ge=0.0)
    charge_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)
    discharge_efficiency: float = Field(default=0.95, gt=0.0, le=1.0)


class EnergyConfig(StrictModel):
    house_load_power_entity_id: str | None = None
    grid_import_power_entity_id: str | None = None
    grid_export_power_entity_id: str | None = None
    pv_power_total_entity_id: str | None = None
    pv_power_1_entity_id: str | None = None
    pv_power_2_entity_id: str | None = None


class ForecastSolarConfig(StrictModel):
    enabled: bool = False
    power_now_entity_id: str | None = None
    energy_current_hour_entity_id: str | None = None
    energy_next_hour_entity_id: str | None = None
    energy_production_today_entity_id: str | None = None
    energy_production_today_remaining_entity_id: str | None = None
    energy_production_tomorrow_entity_id: str | None = None
    power_highest_peak_time_today_entity_id: str | None = None
    power_highest_peak_time_tomorrow_entity_id: str | None = None


class AppConfigModel(StrictModel):
    dph: float = Field(default=0.0, ge=0.0, le=100.0)
    price_provider: Literal["spotovaelektrina", "ote"] = Field(default=DEFAULT_PRICE_PROVIDER)
    poplatky: PoplatkyConfig = Field(default_factory=PoplatkyConfig)
    fixni: FixniConfig = Field(default_factory=FixniConfig)
    tarif: TarifConfig = Field(default_factory=TarifConfig)
    influxdb: InfluxDbConfig = Field(default_factory=InfluxDbConfig)
    prodej: ProdejConfig = Field(default_factory=ProdejConfig)
    battery: BatteryConfig = Field(default_factory=BatteryConfig)
    energy: EnergyConfig = Field(default_factory=EnergyConfig)
    forecast_solar: ForecastSolarConfig = Field(default_factory=ForecastSolarConfig)

    @field_validator("dph", mode="before")
    @classmethod
    def normalize_dph(cls, value):
        return normalize_dph_percent(value)

    @field_validator("price_provider", mode="before")
    @classmethod
    def normalize_provider(cls, value):
        return normalize_price_provider(value)
