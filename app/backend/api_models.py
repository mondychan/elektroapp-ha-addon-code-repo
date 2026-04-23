from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from datetime import datetime


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FeesHistoryUpdateRequest(ApiModel):
    history: list[dict[str, Any]]


class PndBackfillRequest(ApiModel):
    range: Literal["yesterday", "week", "month", "year", "max"]


class HpResolveEntityRequest(ApiModel):
    entity_id: str = Field(min_length=1)


class PricesRefreshRequest(ApiModel):
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None):
        if value is not None:
            datetime.strptime(value, "%Y-%m-%d")
        return value


class CacheInvalidateRequest(ApiModel):
    domain: Literal["prices", "consumption", "export", "pnd", "all"]
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None):
        if value is not None:
            datetime.strptime(value, "%Y-%m-%d")
        return value


class RecommendationQuery(ApiModel):
    date: str | None = None

    @field_validator("date")
    @classmethod
    def validate_date(cls, value: str | None):
        if value is not None:
            datetime.strptime(value, "%Y-%m-%d")
        return value
