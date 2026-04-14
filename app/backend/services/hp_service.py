from __future__ import annotations

import re
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
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

    def get_data(self, period: str | None, anchor: str | None, cfg: dict[str, Any], tzinfo) -> dict[str, Any]:
        hp_cfg = self._get_hp_cfg(cfg)
        effective_period = period or "day"
        effective_anchor = self._normalize_anchor(effective_period, anchor, tzinfo)
        chart_start_utc, chart_end_utc, chart_interval = self._resolve_range(effective_period, effective_anchor, cfg, tzinfo)
        kpi_anchor = datetime.now(tzinfo).strftime("%Y-%m-%d")
        result = {
            "date": effective_anchor if effective_period == "day" else None,
            "period": effective_period,
            "anchor": effective_anchor,
            "kpi_date": kpi_anchor,
            "config": {
                "enabled": hp_cfg.get("enabled", False),
                "entities": [],
            },
            "kpis": [],
            "status_cards": [],
            "charts": [],
        }
        if not hp_cfg.get("enabled", False):
            return result

        resolved_entities = self.resolve_effective_entities(hp_cfg)
        if not resolved_entities:
            return result

        influx = self._get_influx_cfg(cfg)

        for raw_entity in resolved_entities:
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
                chart_start_utc,
                chart_end_utc,
                chart_interval,
                tzinfo,
                effective_anchor,
                effective_period,
            )
            if numeric_payload.get("chart", {}).get("points"):
                self.logger.info(
                    "HP entity chart found data: entity_id=%s measurement=%s",
                    entity.get("entity_id"),
                    numeric_payload.get("chart", {}).get("measurement")
                )

            if entity.get("kpi_enabled", True):
                result["kpis"].append(numeric_payload["kpi"])
            if entity.get("chart_enabled"):
                result["charts"].append(numeric_payload["chart"])

        return result

    def resolve_effective_entities(self, hp_cfg: dict[str, Any]) -> list[dict[str, Any]]:
        source_mode = hp_cfg.get("source_mode", "manual")
        if source_mode == "manual":
            return [self._apply_smart_defaults(dict(e)) for e in hp_cfg.get("entities", [])]

        manual_entities = [dict(entity) for entity in hp_cfg.get("entities", [])]
        discovered = self._discover_entities(hp_cfg, source_mode)
        final_entities_by_id: dict[str, dict[str, Any]] = {}

        for entity in discovered:
            final_entities_by_id[str(entity.get("entity_id"))] = entity

        for entity in manual_entities:
            entity_id = str(entity.get("entity_id") or "").strip()
            if not entity_id:
                continue
            final_entities_by_id[entity_id] = self._apply_smart_defaults(entity)

        return list(final_entities_by_id.values())

    def _discover_entities(self, hp_cfg: dict[str, Any], source_mode: str) -> list[dict[str, Any]]:
        scan_cfg = hp_cfg.get("scan", {})
        defaults_cfg = hp_cfg.get("defaults", {})
        overrides = hp_cfg.get("overrides", [])

        try:
            states = self._home_assistant_service.get_states()
        except Exception as exc:
            self.logger.warning("Failed to fetch states for HP auto-discovery: %s", exc)
            return []

        prefix = scan_cfg.get("prefix", "")
        regex_pattern = scan_cfg.get("regex", "")
        include_domains = scan_cfg.get("include_domains", ["sensor", "binary_sensor"])
        allowlist = set(scan_cfg.get("allowlist", []))
        blocklist = set(scan_cfg.get("blocklist", []))
        exclude_unavailable = scan_cfg.get("exclude_unavailable", True)

        regex_matcher = None
        if source_mode == "regex" and regex_pattern:
            try:
                regex_matcher = re.compile(regex_pattern)
            except re.error:
                self.logger.warning("Invalid regex for HP auto-discovery: %s", regex_pattern)

        discovered = []
        for state_obj in states:
            entity_id = state_obj.get("entity_id", "")
            if not entity_id:
                continue

            domain = entity_id.split(".")[0]
            if include_domains and domain not in include_domains:
                continue

            if allowlist and entity_id not in allowlist:
                continue
            if entity_id in blocklist:
                continue

            if exclude_unavailable and state_obj.get("state") in ("unavailable", "unknown"):
                continue

            if source_mode == "prefix":
                if prefix and not entity_id.startswith(prefix):
                    continue
            elif source_mode == "regex":
                if regex_matcher is None or not regex_matcher.search(entity_id):
                    continue

            metadata = self._home_assistant_service.resolve_metadata_from_state(state_obj)

            is_numeric = metadata.get("display_kind") == "numeric"
            kpi_enabled = defaults_cfg.get("kpi_enabled", True)
            chart_enabled = defaults_cfg.get("chart_enabled_numeric", True) if is_numeric else defaults_cfg.get("chart_enabled_state", False)
            kpi_mode = defaults_cfg.get("kpi_mode_numeric", "last") if is_numeric else defaults_cfg.get("kpi_mode_state", "last")
            decimals = defaults_cfg.get("decimals")

            entity_cfg = self._apply_smart_defaults({
                "entity_id": metadata["entity_id"],
                "label": metadata["label"],
                "display_kind": metadata["display_kind"],
                "source_kind": metadata["source_kind"],
                "kpi_enabled": kpi_enabled,
                "chart_enabled": chart_enabled,
                "kpi_mode": kpi_mode,
                "unit": metadata["unit"],
                "decimals": decimals,
                "device_class": metadata["device_class"],
                "state_class": metadata["state_class"]
            })

            if entity_cfg["source_kind"] == "counter" and kpi_mode not in ("last", "sum", "delta"):
                entity_cfg["kpi_mode"] = "delta"
            elif entity_cfg["source_kind"] == "instant" and kpi_mode not in ("last", "min", "max", "avg"):
                entity_cfg["kpi_mode"] = "last"
            elif entity_cfg["source_kind"] == "state":
                entity_cfg["kpi_mode"] = "last"

            discovered.append(entity_cfg)

        override_map = {o["entity_id"]: o for o in overrides}
        final_entities = []
        for ent in discovered:
            eid = ent["entity_id"]
            if eid in override_map:
                override = override_map[eid]
                if not override.get("enabled", True):
                    continue
                for k, v in override.items():
                    if k not in ("entity_id", "enabled") and v is not None:
                        ent[k] = v
            final_entities.append(ent)

        return final_entities

    def _apply_smart_defaults(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Automatically detect logical units based on ID/Unit if not explicitly set."""
        eid = str(entity.get("entity_id") or "").lower()
        unit = str(entity.get("unit") or "").lower()

        # Only apply if value_format is not already defined in config/override
        if entity.get("value_format"):
            return entity

        # Duration detection
        if unit == "s" or any(x in eid for x in ("seconds", "uptime", "runtime")):
            entity["value_format"] = "duration_seconds"
        elif unit in ("min", "m") or "minutes" in eid:
             # Heuristic to avoid physical length/range collision with 'm' (meters)
             if not (unit == "m" and any(x in eid for x in ("distance", "length", "range"))):
                entity["value_format"] = "duration_minutes"
        elif unit in ("h", "hours") or "hours" in eid:
            entity["value_format"] = "duration_hours"
        # Power and Energy auto-scaling detection
        elif unit in ("w", "wh", "kwh", "va"):
            entity["value_format"] = "auto_unit"

        if entity.get("value_format") and not entity.get("duration_style"):
            entity["duration_style"] = "short"
            entity["duration_max_parts"] = 2

        return entity

    def _normalize_anchor(self, period: str, anchor: str | None, tzinfo) -> str:
        now_local = datetime.now(tzinfo)
        if period == "year":
            if anchor:
                return anchor
            return str(now_local.year)
        if period == "month":
            if anchor:
                return anchor
            return now_local.strftime("%Y-%m")
        if anchor:
            return anchor
        return now_local.strftime("%Y-%m-%d")

    def _resolve_range(self, period: str, anchor: str, cfg: dict[str, Any], tzinfo) -> tuple[datetime, datetime, str]:
        influx = self._get_influx_cfg(cfg)
        if period == "day":
            start_utc, end_utc = self._parse_time_range(anchor, None, None, tzinfo)
            return start_utc, end_utc, influx.get("interval", "15m")
        if period == "week":
            anchor_local = datetime.strptime(anchor, "%Y-%m-%d").replace(tzinfo=tzinfo)
            start_local = anchor_local - timedelta(days=6)
            end_local = anchor_local + timedelta(days=1)
            return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), "1h"
        if period == "month":
            anchor_local = datetime.strptime(anchor, "%Y-%m").replace(tzinfo=tzinfo)
            if anchor_local.month == 12:
                end_local = anchor_local.replace(year=anchor_local.year + 1, month=1)
            else:
                end_local = anchor_local.replace(month=anchor_local.month + 1)
            return anchor_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), "6h"
        anchor_year = int(anchor)
        start_local = datetime(anchor_year, 1, 1, tzinfo=tzinfo)
        end_local = datetime(anchor_year + 1, 1, 1, tzinfo=tzinfo)
        return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), "1w"

    def _measurement_candidates(self, influx: dict[str, Any], entity: dict[str, Any], metadata: dict[str, Any] | None = None) -> list[str] | None:
        """Heuristic to find matching InfluxDB measurement names."""
        candidates = []

        # 1. Explicit measurement from config
        measurement = entity.get("measurement")
        if measurement:
            candidates.append(measurement)

        # 2. Entity ID (The most common one for HA integrations)
        entity_id = entity.get("entity_id")
        if entity_id:
            candidates.append(entity_id)
            if "_" in entity_id:
                candidates.append(entity_id.replace("_", "-"))
            if "." in entity_id:
                # E.g. sensor.global_uptime -> global_uptime
                sub = entity_id.split(".", 1)[1]
                candidates.append(sub)
                if "_" in sub:
                     candidates.append(sub.replace("_", "-"))
                     # Try the last part: ebusd_ha_daemon_global_uptime -> uptime
                     candidates.append(sub.split("_")[-1])

        # 3. Attributes heuristics
        display_kind = entity.get("display_kind") or (metadata.get("display_kind") if metadata else None)
        source_kind = entity.get("source_kind") or (metadata.get("source_kind") if metadata else None)
        raw_unit = str(entity.get("unit") or (metadata or {}).get("unit") or "").strip()
        unit = raw_unit.lower()
        device_class = str(entity.get("device_class") or (metadata or {}).get("device_class") or "").strip().lower()
        state_class = str(entity.get("state_class") or (metadata or {}).get("state_class") or "").strip().lower()

        if display_kind == "state" or source_kind == "state":
            candidates.append("state")
        elif unit in {"w", "kw"} or device_class == "power":
            candidates.extend(["W", "kW"])
        elif unit in {"wh", "kwh"} or device_class == "energy" or source_kind == "counter" or state_class in {"total", "total_increasing"}:
            candidates.extend(["kWh", "Wh"])
        elif raw_unit:
            candidates.append(raw_unit)
            if unit and unit != raw_unit:
                candidates.append(unit)

        # 4. Common HA InfluxDB fallbacks
        if "state" not in candidates:
            candidates.append("state")
        
        # 5. Global config fallback
        if influx and influx.get("measurement"):
            candidates.append(influx.get("measurement"))

        return candidates if candidates else None

    def _build_state_card(self, influx: dict[str, Any], entity: dict[str, Any], metadata: dict[str, Any] | None, tzinfo):
        measurement_candidates = self._measurement_candidates(influx, entity, metadata)
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

        return {
            "entity_id": entity.get("entity_id"),
            "label": entity.get("label"),
            "value": display_value,
            "raw_value": raw_value,
            "unit": entity.get("unit"),
            "updated_at": updated_at,
            "device_class": entity.get("device_class"),
            "state_class": entity.get("state_class"),
            "value_format": entity.get("value_format"),
            "duration_style": entity.get("duration_style"),
            "duration_max_parts": entity.get("duration_max_parts"),
        }

    def _build_numeric_payload(
        self,
        influx: dict[str, Any],
        entity: dict[str, Any],
        metadata: dict[str, Any] | None,
        chart_start_utc: datetime,
        chart_end_utc: datetime,
        chart_interval: str,
        tzinfo,
        effective_anchor: str,
        effective_period: str,
    ) -> dict[str, Any]:
        measurement_candidates = self._measurement_candidates(influx, entity, metadata)
        aggregate_fn = "mean" if entity.get("source_kind") == "instant" else "last"
        raw_chart_points = self._query_entity_series(
            influx,
            entity.get("entity_id"),
            chart_start_utc,
            chart_end_utc,
            interval=chart_interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=measurement_candidates,
            aggregate_fn=aggregate_fn,
        )
        chart_points = self._build_chart_points(
            raw_chart_points=raw_chart_points,
            chart_start_utc=chart_start_utc,
            chart_end_utc=chart_end_utc,
            chart_interval=chart_interval,
            period=effective_period,
            source_kind=str(entity.get("source_kind") or "instant"),
            tzinfo=tzinfo,
        )
        clean_period_points = [{"time": p.get("time"), "value": p.get("value")} for p in raw_chart_points if p.get("value") is not None]
        period_values = [p["value"] for p in clean_period_points]
        kpi_mode = entity.get("kpi_mode") or "last"
        decimals = entity.get("decimals")

        latest_record = self._safe_query_entity_last_value(
            influx,
            entity.get("entity_id"),
            tzinfo=tzinfo,
            numeric=True,
            label=entity.get("label"),
            measurement_candidates=measurement_candidates,
        )
        latest_value = _safe_float(latest_record.get("value")) if latest_record else (period_values[-1] if period_values else None)

        if latest_value is None and metadata:
            latest_value = _safe_float(metadata.get("state"))

        kpi_value = self._compute_kpi_value(kpi_mode, period_values, latest_value)
        stats = self._compute_stats(period_values, latest_value, decimals)
        updated_at = latest_record.get("time") if latest_record else (clean_period_points[-1]["time"] if clean_period_points else None)
        if not clean_period_points:
            self.logger.info(
                "HP entity chart has no data from InfluxDB: entity_id=%s period=%s anchor=%s tried_measurements=%s",
                entity.get("entity_id"),
                effective_period,
                effective_anchor,
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
                "value_format": entity.get("value_format"),
                "duration_style": entity.get("duration_style"),
                "duration_max_parts": entity.get("duration_max_parts"),
                "secondary_metrics": self._build_secondary_metrics(kpi_mode, stats),
            },
            "chart": {
                "entity_id": entity.get("entity_id"),
                "label": entity.get("label"),
                "unit": entity.get("unit"),
                "decimals": decimals,
                "source_kind": entity.get("source_kind"),
                "value_format": entity.get("value_format"),
                "duration_style": entity.get("duration_style"),
                "duration_max_parts": entity.get("duration_max_parts"),
                "points": chart_points,
            },
        }

    def _build_chart_points(
        self,
        raw_chart_points: list[dict[str, Any]],
        chart_start_utc: datetime,
        chart_end_utc: datetime,
        chart_interval: str,
        period: str,
        source_kind: str,
        tzinfo,
    ) -> list[dict[str, Any]]:
        normalized_points = [{"time": p.get("time"), "value": p.get("value")} for p in raw_chart_points]
        if period == "day":
            return self._fill_fixed_interval_points(
                points=normalized_points,
                start_utc=chart_start_utc,
                end_utc=chart_end_utc,
                interval=chart_interval,
                tzinfo=tzinfo,
            )

        buckets: dict[str, list[float]] = {}
        for point in normalized_points:
            if point.get("value") is None or not point.get("time"):
                continue
            point_dt = datetime.fromisoformat(str(point["time"]))
            bucket_dt = self._bucket_start_for_period(point_dt, period)
            bucket_key = bucket_dt.isoformat()
            buckets.setdefault(bucket_key, []).append(float(point["value"]))

        filled_points: list[dict[str, Any]] = []
        for bucket_dt in self._iter_period_buckets(chart_start_utc, chart_end_utc, period, tzinfo):
            bucket_key = bucket_dt.isoformat()
            values = buckets.get(bucket_key, [])
            if not values:
                bucket_value = None
            elif source_kind == "counter":
                bucket_value = values[-1]
            else:
                bucket_value = sum(values) / len(values)
            filled_points.append({"time": bucket_key, "value": bucket_value})
        return filled_points

    def _fill_fixed_interval_points(
        self,
        points: list[dict[str, Any]],
        start_utc: datetime,
        end_utc: datetime,
        interval: str,
        tzinfo,
    ) -> list[dict[str, Any]]:
        step = self._parse_interval(interval)
        value_map = {str(point.get("time")): point.get("value") for point in points if point.get("time")}
        filled_points: list[dict[str, Any]] = []
        current_utc = start_utc
        while current_utc < end_utc:
            current_local = current_utc.astimezone(tzinfo)
            key = current_local.isoformat()
            filled_points.append({"time": key, "value": value_map.get(key)})
            current_utc += step
        return filled_points

    def _bucket_start_for_period(self, dt_local: datetime, period: str) -> datetime:
        if period in {"week", "month"}:
            return dt_local.replace(hour=0, minute=0, second=0, microsecond=0)
        if period == "year":
            return dt_local.replace(month=dt_local.month, day=1, hour=0, minute=0, second=0, microsecond=0)
        return dt_local

    def _iter_period_buckets(self, start_utc: datetime, end_utc: datetime, period: str, tzinfo):
        current = start_utc.astimezone(tzinfo)
        end_local = end_utc.astimezone(tzinfo)
        if period in {"week", "month"}:
            current = current.replace(hour=0, minute=0, second=0, microsecond=0)
            while current < end_local:
                yield current
                current += timedelta(days=1)
            return
        current = current.replace(month=1 if period == "year" else current.month, day=1, hour=0, minute=0, second=0, microsecond=0)
        while current < end_local:
            yield current
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)

    def _parse_interval(self, interval: str) -> timedelta:
        raw = str(interval or "15m").strip().lower()
        if raw.endswith("m"):
            return timedelta(minutes=int(raw[:-1] or 15))
        if raw.endswith("h"):
            return timedelta(hours=int(raw[:-1] or 1))
        if raw.endswith("d"):
            return timedelta(days=int(raw[:-1] or 1))
        if raw.endswith("w"):
            return timedelta(weeks=int(raw[:-1] or 1))
        return timedelta(minutes=15)

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
