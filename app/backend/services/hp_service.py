from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class HPService:
    def __init__(
        self,
        get_influx_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        get_hp_cfg: Callable[[dict[str, Any]], dict[str, Any]],
        parse_time_range: Callable[..., tuple[datetime, datetime]],
        query_entity_series: Callable[..., list[dict[str, Any]]],
        safe_query_entity_last_value: Callable[..., dict[str, Any] | None],
        home_assistant_service,
        logger,
    ):
        self._get_influx_cfg = get_influx_cfg
        self._get_hp_cfg = get_hp_cfg
        self._parse_time_range = parse_time_range
        self._query_entity_series = query_entity_series
        self._safe_query_entity_last_value = safe_query_entity_last_value
        self._home_assistant_service = home_assistant_service
        self.logger = logger

    def resolve_entity(self, entity_id: str) -> dict[str, Any]:
        return self._home_assistant_service.resolve_entity_metadata(entity_id)

    def get_data(self, date: str | None, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        hp_cfg = self._get_hp_cfg(cfg)
        effective_date = date or datetime.now(tzinfo).strftime("%Y-%m-%d")
        result = {
            "date": effective_date,
            "config": {
                "enabled": hp_cfg.get("enabled", False),
                "entities": [],
            },
            "kpis": [],
            "status_cards": [],
            "charts": [],
        }
        if not hp_cfg.get("entities"):
            return result

        influx = self._get_influx_cfg(cfg)
        start_utc, end_utc = self._parse_time_range(effective_date, None, None, tzinfo)
        interval = influx.get("interval", "15m")

        for raw_entity in hp_cfg.get("entities", []):
            entity = dict(raw_entity)
            metadata = self._home_assistant_service.resolve_entity_metadata_safe(entity.get("entity_id"))
            if metadata:
                if not entity.get("label"):
                    entity["label"] = metadata.get("label")
                if not entity.get("unit"):
                    entity["unit"] = metadata.get("unit")
                if not entity.get("device_class"):
                    entity["device_class"] = metadata.get("device_class")
                if not entity.get("state_class"):
                    entity["state_class"] = metadata.get("state_class")
                if entity.get("display_kind") not in {"numeric", "state"}:
                    entity["display_kind"] = metadata.get("display_kind")
                if entity.get("source_kind") not in {"instant", "counter", "state"}:
                    entity["source_kind"] = metadata.get("source_kind")
                if not entity.get("kpi_mode"):
                    entity["kpi_mode"] = metadata.get("kpi_mode")
            entity["label"] = entity.get("label") or entity.get("entity_id")
            result["config"]["entities"].append(entity)

            if entity.get("display_kind") == "state":
                status_card = self._build_state_card(influx, entity, metadata, tzinfo)
                if entity.get("kpi_enabled", True):
                    result["status_cards"].append(status_card)
                continue

            numeric_payload = self._build_numeric_payload(influx, entity, start_utc, end_utc, interval, tzinfo)
            if entity.get("kpi_enabled", True):
                result["kpis"].append(numeric_payload["kpi"])
            if entity.get("chart_enabled"):
                result["charts"].append(numeric_payload["chart"])

        return result

    def _measurement_candidates(self, entity: dict[str, Any]) -> list[str] | None:
        measurement = entity.get("measurement")
        if measurement:
            return [measurement]
        return None

    def _build_state_card(self, influx: dict[str, Any], entity: dict[str, Any], metadata: dict[str, Any] | None, tzinfo):
        record = self._safe_query_entity_last_value(
            influx,
            entity.get("entity_id"),
            tzinfo=tzinfo,
            numeric=False,
            label=entity.get("label"),
            measurement_candidates=self._measurement_candidates(entity),
        )
        raw_value = None
        updated_at = None
        if record:
            raw_value = record.get("raw_value")
            updated_at = record.get("time")
        if raw_value is None and metadata:
            raw_value = metadata.get("state")
        if isinstance(raw_value, bool):
            display_value = "Zapnuto" if raw_value else "Vypnuto"
        else:
            normalized = str(raw_value).strip() if raw_value is not None else "-"
            if normalized.lower() in {"on", "true"}:
                display_value = "Zapnuto"
            elif normalized.lower() in {"off", "false"}:
                display_value = "Vypnuto"
            else:
                display_value = normalized or "-"
        return {
            "entity_id": entity.get("entity_id"),
            "label": entity.get("label"),
            "value": display_value,
            "raw_value": raw_value,
            "unit": entity.get("unit"),
            "updated_at": updated_at,
            "device_class": entity.get("device_class"),
            "state_class": entity.get("state_class"),
        }

    def _build_numeric_payload(
        self,
        influx: dict[str, Any],
        entity: dict[str, Any],
        start_utc: datetime,
        end_utc: datetime,
        interval: str,
        tzinfo,
    ) -> dict[str, Any]:
        points = self._query_entity_series(
            influx,
            entity.get("entity_id"),
            start_utc,
            end_utc,
            interval=interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=self._measurement_candidates(entity),
        )
        clean_points = [{"time": p.get("time"), "value": p.get("value")} for p in points if p.get("value") is not None]
        values = [p["value"] for p in clean_points]
        kpi_mode = entity.get("kpi_mode") or "last"
        decimals = entity.get("decimals")

        latest_record = None
        if kpi_mode == "last" and not values:
            latest_record = self._safe_query_entity_last_value(
                influx,
                entity.get("entity_id"),
                tzinfo=tzinfo,
                numeric=True,
                label=entity.get("label"),
                measurement_candidates=self._measurement_candidates(entity),
            )
            latest_value = _safe_float(latest_record.get("value")) if latest_record else None
        else:
            latest_value = values[-1] if values else None

        kpi_value = self._compute_kpi_value(kpi_mode, values, latest_value)
        updated_at = latest_record.get("time") if latest_record else (clean_points[-1]["time"] if clean_points else None)

        return {
            "kpi": {
                "entity_id": entity.get("entity_id"),
                "label": entity.get("label"),
                "value": kpi_value,
                "unit": entity.get("unit"),
                "decimals": decimals,
                "kpi_mode": kpi_mode,
                "source_kind": entity.get("source_kind"),
                "updated_at": updated_at,
            },
            "chart": {
                "entity_id": entity.get("entity_id"),
                "label": entity.get("label"),
                "unit": entity.get("unit"),
                "decimals": decimals,
                "source_kind": entity.get("source_kind"),
                "points": clean_points,
            },
        }

    def _compute_kpi_value(self, kpi_mode: str, values: list[float], latest_value: float | None) -> float | None:
        if kpi_mode == "last":
            return latest_value
        if not values:
            return None
        if kpi_mode == "min":
            return min(values)
        if kpi_mode == "max":
            return max(values)
        if kpi_mode == "avg":
            return sum(values) / len(values)
        if kpi_mode == "delta":
            return values[-1] - values[0]
        if kpi_mode == "sum":
            total = 0.0
            for previous, current in zip(values, values[1:]):
                diff = current - previous
                if diff >= 0:
                    total += diff
            return total
        return latest_value
