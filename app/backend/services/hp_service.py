from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_if_needed(value: float | None, decimals: int | None) -> float | None:
    if value is None:
        return None
    if decimals is None:
        return value
    return round(value, decimals)


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

            numeric_payload = self._build_numeric_payload(
                influx,
                entity,
                metadata,
                start_utc,
                end_utc,
                interval,
                tzinfo,
                effective_date,
            )
            if entity.get("kpi_enabled", True):
                result["kpis"].append(numeric_payload["kpi"])
            if entity.get("chart_enabled"):
                result["charts"].append(numeric_payload["chart"])

        return result

    def _measurement_candidates(self, entity: dict[str, Any], metadata: dict[str, Any] | None = None) -> list[str] | None:
        measurement = entity.get("measurement")
        if measurement:
            return [measurement]

        display_kind = entity.get("display_kind") or metadata.get("display_kind") if metadata else entity.get("display_kind")
        source_kind = entity.get("source_kind") or metadata.get("source_kind") if metadata else entity.get("source_kind")
        unit = (entity.get("unit") or (metadata or {}).get("unit") or "").strip().lower()
        device_class = str(entity.get("device_class") or (metadata or {}).get("device_class") or "").strip().lower()
        state_class = str(entity.get("state_class") or (metadata or {}).get("state_class") or "").strip().lower()

        if display_kind == "state" or source_kind == "state":
            return ["state"]
        if unit in {"w", "kw"} or device_class == "power":
            return ["W", "kW"]
        if unit in {"wh", "kwh"} or device_class == "energy" or source_kind == "counter" or state_class in {"total", "total_increasing"}:
            return ["kWh", "Wh"]
        if unit:
            return [unit]
        return None

    def _build_state_card(self, influx: dict[str, Any], entity: dict[str, Any], metadata: dict[str, Any] | None, tzinfo):
        measurement_candidates = self._measurement_candidates(entity, metadata)
        record = self._safe_query_entity_last_value(
            influx,
            entity.get("entity_id"),
            tzinfo=tzinfo,
            numeric=False,
            label=entity.get("label"),
            measurement_candidates=measurement_candidates,
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
        if raw_value is None:
            self.logger.info(
                "HP state entity returned no data: entity_id=%s measurement_candidates=%s",
                entity.get("entity_id"),
                measurement_candidates or [influx.get("measurement")],
            )
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
        metadata: dict[str, Any] | None,
        start_utc: datetime,
        end_utc: datetime,
        interval: str,
        tzinfo,
        effective_date: str,
    ) -> dict[str, Any]:
        measurement_candidates = self._measurement_candidates(entity, metadata)
        points = self._query_entity_series(
            influx,
            entity.get("entity_id"),
            start_utc,
            end_utc,
            interval=interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=measurement_candidates,
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
                measurement_candidates=measurement_candidates,
            )
            latest_value = _safe_float(latest_record.get("value")) if latest_record else None
        else:
            latest_value = values[-1] if values else None

        if latest_value is None and metadata:
            latest_value = _safe_float(metadata.get("state"))

        kpi_value = self._compute_kpi_value(kpi_mode, values, latest_value)
        stats = self._compute_stats(values, latest_value, decimals)
        updated_at = latest_record.get("time") if latest_record else (clean_points[-1]["time"] if clean_points else None)
        if not clean_points and latest_value is None:
            self.logger.info(
                "HP numeric entity returned no data: entity_id=%s date=%s measurement_candidates=%s",
                entity.get("entity_id"),
                effective_date,
                measurement_candidates or [influx.get("measurement")],
            )

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
                "secondary_metrics": self._build_secondary_metrics(kpi_mode, stats),
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

    def _compute_stats(self, values: list[float], latest_value: float | None, decimals: int | None) -> dict[str, float | None]:
        return {
            "last": _round_if_needed(latest_value, decimals),
            "avg": _round_if_needed(sum(values) / len(values), decimals) if values else None,
            "min": _round_if_needed(min(values), decimals) if values else None,
            "max": _round_if_needed(max(values), decimals) if values else None,
        }

    def _build_secondary_metrics(self, primary_mode: str, stats: dict[str, float | None]) -> list[dict[str, float | None | str]]:
        order_map = {
            "last": ["avg", "min", "max"],
            "avg": ["last", "min", "max"],
            "min": ["last", "avg", "max"],
            "max": ["last", "avg", "min"],
            "delta": ["last", "avg", "max"],
            "sum": ["last", "avg", "max"],
        }
        order = order_map.get(primary_mode, ["avg", "min", "max"])
        labels = {
            "last": "LAST",
            "avg": "AVG",
            "min": "MIN",
            "max": "MAX",
        }
        return [
            {"key": key, "label": labels[key], "value": stats.get(key)}
            for key in order
            if key in labels and stats.get(key) is not None
        ]
