from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class QueryModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _parse_iso8601(value: str):
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized)


class OptionalDateQuery(QueryModel):
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None):
        if value is None:
            return value
        datetime.strptime(value, "%Y-%m-%d")
        return value


class DateRangeQuery(QueryModel):
    date: str | None = None
    start: str | None = None
    end: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None):
        if value is None:
            return value
        datetime.strptime(value, "%Y-%m-%d")
        return value

    @field_validator("start", "end")
    @classmethod
    def validate_iso(cls, value: str | None):
        if value is None:
            return value
        _parse_iso8601(value)
        return value

    @model_validator(mode="after")
    def validate_range_pair(self):
        if (self.start and not self.end) or (self.end and not self.start):
            raise ValueError("Both start and end must be provided together.")
        return self


class MonthQuery(QueryModel):
    month: str

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str):
        datetime.strptime(value, "%Y-%m")
        return value


class HeatmapQuery(QueryModel):
    month: str
    metric: Literal["price", "buy", "export"] = "buy"

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str):
        datetime.strptime(value, "%Y-%m")
        return value


class EnergyBalanceQuery(QueryModel):
    period: Literal["week", "month", "year"] = "week"
    anchor: str | None = None

    @model_validator(mode="after")
    def validate_anchor_for_period(self):
        if self.anchor is None:
            return self
        if self.period == "week":
            datetime.strptime(self.anchor, "%Y-%m-%d")
        elif self.period == "month":
            datetime.strptime(self.anchor, "%Y-%m")
        else:
            if len(self.anchor) != 4:
                raise ValueError("Invalid anchor for year. Use YYYY.")
            int(self.anchor)
        return self
