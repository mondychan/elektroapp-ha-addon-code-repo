from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
import requests

from api import to_rfc3339
from influx import (
    build_influx_from_clause_for_measurement,
    escape_influx_tag_value,
    quote_influx_identifier,
    validate_influx_aggregate,
    validate_influx_interval,
)
from battery import get_slot_index_for_dt


class InfluxService:
    def __init__(self, logger):
        self.logger = logger
        self.session = requests.Session()
        # Nastavení pooling - 10 spojení v poolu, retry mechanismus
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=10, 
            pool_maxsize=20,
            max_retries=3
        )
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def influx_query(self, influx, query):
        host = influx["host"]
        port = influx.get("port", 8086)
        db = influx["database"]
        url = f"http://{host}:{port}/query"
        params = {"db": db, "q": query, "epoch": "s"}
        username = influx.get("username")
        password = influx.get("password")
        auth = None
        if username and password and password != "CHANGE_ME":
            auth = (username, password)
        
        r = self.session.get(url, params=params, auth=auth, timeout=15)
        r.raise_for_status()
        data = r.json()
        if data.get("results") and data["results"][0].get("error"):
            raise HTTPException(status_code=500, detail=data["results"][0]["error"])
        return data

    def get_measurement_candidates(self, influx, preferred=None):
        configured = influx.get("measurement") if isinstance(influx, dict) else None
        candidates = []

        def _add(value):
            if isinstance(value, str):
                raw = value.strip()
                if raw and raw not in candidates:
                    candidates.append(raw)

        if isinstance(preferred, (list, tuple)):
            for item in preferred:
                _add(item)
        else:
            _add(preferred)
        _add(configured)
        return candidates

    def get_entity_id_candidates(self, entity_id):
        if not isinstance(entity_id, str):
            return []
        raw = entity_id.strip()
        if not raw:
            return []

        candidates = []

        def _add(value):
            if value and value not in candidates:
                candidates.append(value)

        _add(raw)
        if "." in raw:
            _, suffix = raw.split(".", 1)
            _add(suffix)
        else:
            _add(f"sensor.{raw}")
        return candidates

    def query_entity_series(
        self,
        influx,
        entity_id,
        start_utc,
        end_utc,
        interval="15m",
        tzinfo=None,
        numeric=True,
        measurement_candidates=None,
        aggregate_fn="last",
    ):
        if not entity_id:
            return []
        field = quote_influx_identifier(influx["field"])
        values = []
        used_entity_id = None
        used_measurement = None
        aggregate = validate_influx_aggregate(aggregate_fn)
        interval = validate_influx_interval(interval)
        for measurement in self.get_measurement_candidates(influx, measurement_candidates):
            from_clause = build_influx_from_clause_for_measurement(influx, measurement)
            for candidate_entity_id in self.get_entity_id_candidates(entity_id):
                q = (
                    f'SELECT {aggregate}({field}) AS "value" '
                    f"FROM {from_clause} "
                    f"WHERE time >= '{to_rfc3339(start_utc)}' AND time < '{to_rfc3339(end_utc)}' "
                    f'AND "entity_id"=\'{escape_influx_tag_value(candidate_entity_id)}\' '
                    f"GROUP BY time({interval}) fill(null)"
                )
                data = self.influx_query(influx, q)
                series = data.get("results", [{}])[0].get("series", [])
                if series:
                    values = series[0]["values"]
                    used_entity_id = candidate_entity_id
                    used_measurement = measurement
                    break
            if used_entity_id:
                break
        if used_entity_id and used_entity_id != entity_id:
            self.logger.debug("Entity fallback matched for series: %s -> %s", entity_id, used_entity_id)
        if used_measurement and used_measurement != influx.get("measurement"):
            self.logger.debug("Measurement fallback matched for series: %s -> %s", entity_id, used_measurement)
        tz = tzinfo or timezone.utc
        points = []
        for ts, raw_value in values:
            value = raw_value
            if numeric and raw_value is not None:
                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    value = None
            ts_dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            ts_local = ts_dt_utc.astimezone(tz)
            points.append(
                {
                    "time": ts_local.isoformat(),
                    "time_utc": to_rfc3339(ts_dt_utc),
                    "value": value,
                    "unit": used_measurement,
                }
            )
        return points

    def query_entity_last_value(
        self,
        influx,
        entity_id,
        tzinfo=None,
        lookback_hours=72,
        numeric=True,
        measurement_candidates=None,
    ):
        if not entity_id:
            return None
        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=max(1, int(lookback_hours)))
        field = quote_influx_identifier(influx["field"])
        values = []
        used_entity_id = None
        used_measurement = None
        for measurement in self.get_measurement_candidates(influx, measurement_candidates):
            from_clause = build_influx_from_clause_for_measurement(influx, measurement)
            for candidate_entity_id in self.get_entity_id_candidates(entity_id):
                q = (
                    f'SELECT last({field}) AS "value" '
                    f"FROM {from_clause} "
                    f"WHERE time >= '{to_rfc3339(start_utc)}' AND time <= '{to_rfc3339(end_utc)}' "
                    f'AND "entity_id"=\'{escape_influx_tag_value(candidate_entity_id)}\''
                )
                data = self.influx_query(influx, q)
                series = data.get("results", [{}])[0].get("series", [])
                if series and series[0].get("values"):
                    values = series[0]["values"]
                    used_entity_id = candidate_entity_id
                    used_measurement = measurement
                    break
            if used_entity_id:
                break
        if not values:
            return None
        if used_entity_id and used_entity_id != entity_id:
            self.logger.debug("Entity fallback matched for last value: %s -> %s", entity_id, used_entity_id)
        if used_measurement and used_measurement != influx.get("measurement"):
            self.logger.debug("Measurement fallback matched for last value: %s -> %s", entity_id, used_measurement)
        ts, raw_value = values[0]
        value = raw_value
        if numeric and raw_value is not None:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = None
        tz = tzinfo or timezone.utc
        ts_dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return {
            "time": ts_dt_utc.astimezone(tz).isoformat(),
            "time_utc": to_rfc3339(ts_dt_utc),
            "value": value,
            "raw_value": raw_value,
            "unit": used_measurement,
        }

    def safe_query_entity_last_value(
        self,
        influx,
        entity_id,
        tzinfo=None,
        lookback_hours=72,
        numeric=True,
        label=None,
        measurement_candidates=None,
    ):
        try:
            return self.query_entity_last_value(
                influx,
                entity_id,
                tzinfo=tzinfo,
                lookback_hours=lookback_hours,
                numeric=numeric,
                measurement_candidates=measurement_candidates,
            )
        except (HTTPException, requests.RequestException, ValueError, TypeError) as exc:
            self.logger.warning("Optional entity query failed (%s / %s): %s", label or "entity", entity_id, exc)
            return None

    def _record_from_value(self, raw_value, ts, tzinfo, numeric, measurement):
        """Shape one ``last()`` row exactly like :meth:`query_entity_last_value`."""
        value = raw_value
        if numeric and raw_value is not None:
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                value = None
        tz = tzinfo or timezone.utc
        ts_dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return {
            "time": ts_dt_utc.astimezone(tz).isoformat(),
            "time_utc": to_rfc3339(ts_dt_utc),
            "value": value,
            "raw_value": raw_value,
            "unit": measurement,
        }

    def query_entity_last_values(
        self,
        influx,
        entities,
        tzinfo=None,
        lookback_hours=72,
        numeric=True,
        measurement_candidates=None,
    ):
        """Batch variant of :meth:`query_entity_last_value`.

        ``entities`` maps a caller-chosen key to the spec of one entity::

            {"soc": {"entity_id": "sensor.x", "measurements": ["%", "percent"]},
             "pv":  {"entity_id": "sensor.y"}}          # falls back to shared list

        All entities of one measurement are resolved with a *single* InfluxQL
        request (``GROUP BY "entity_id"``) instead of one HTTP round-trip per
        entity, which is what makes the once-per-second live dashboard safe for
        a Home Assistant host.  Missing entities simply do not appear in the
        result; keys with an empty ``entity_id`` are skipped.
        """
        specs = {
            key: spec
            for key, spec in (entities or {}).items()
            if isinstance(spec, dict) and isinstance(spec.get("entity_id"), str) and spec["entity_id"].strip()
        }
        if not specs:
            return {}

        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(hours=max(1, int(lookback_hours)))
        field = quote_influx_identifier(influx["field"])

        # requested entity id -> caller key(s)
        owners = {}
        for key, spec in specs.items():
            owners.setdefault(spec["entity_id"], []).append(key)

        # Candidate id -> (requested id, measurement).  Candidate spellings come from
        # the same helper the per-entity query uses, so both paths agree.
        candidates = {}
        for key, spec in specs.items():
            measurements = spec.get("measurements")
            for measurement in self.get_measurement_candidates(
                influx, measurements if measurements is not None else measurement_candidates
            ):
                for candidate in self.get_entity_id_candidates(spec["entity_id"]):
                    candidates.setdefault(candidate, (spec["entity_id"], measurement))

        resolved = {}
        pending_measurements = [c[1] for c in candidates.values()]
        # Preserve candidate order (preferred list first, configured last) while
        # de-duplicating the measurements.
        ordered_measurements = []
        for measurement in pending_measurements:
            if measurement not in ordered_measurements:
                ordered_measurements.append(measurement)

        unresolved = set(specs)
        for measurement in ordered_measurements:
            if not unresolved:
                break
            ids = [
                candidate
                for candidate, (owner, candidate_measurement) in candidates.items()
                if candidate_measurement == measurement
            ]
            if not ids:
                continue
            from_clause = build_influx_from_clause_for_measurement(influx, measurement)
            predicate = " OR ".join(
                f'"entity_id"=\'{escape_influx_tag_value(candidate)}\'' for candidate in ids
            )
            q = (
                f'SELECT last({field}) AS "value" '
                f"FROM {from_clause} "
                f"WHERE time >= '{to_rfc3339(start_utc)}' AND time <= '{to_rfc3339(end_utc)}' "
                f"AND ({predicate}) "
                f'GROUP BY "entity_id"'
            )
            try:
                data = self.influx_query(influx, q)
            except (HTTPException, requests.RequestException, ValueError, TypeError) as exc:
                self.logger.warning("Batch last-value query failed for measurement %s: %s", measurement, exc)
                continue
            series_list = data.get("results", [{}])[0].get("series") or []
            for series in series_list:
                matched = (series.get("tags") or {}).get("entity_id")
                if not matched or matched not in candidates:
                    continue
                owner_entity = candidates[matched][0]
                for key in owners.get(owner_entity, []):
                    if key in resolved:
                        continue
                    spec = specs[key]
                    entity_numeric = spec.get("numeric", numeric)
                    values = series.get("values") or []
                    if not values:
                        continue
                    # ``SELECT last(...) ... GROUP BY "entity_id"`` yields one
                    # ``[timestamp, value]`` row per series; be tolerant of a bare
                    # scalar as well.
                    row = values[-1]
                    if isinstance(row, (list, tuple)):
                        ts, raw_value = row[0], row[-1]
                    else:
                        ts, raw_value = values[0], row
                    resolved[key] = self._record_from_value(
                        raw_value, ts, tzinfo, entity_numeric, measurement
                    )
                    unresolved.discard(key)
        return resolved

    def safe_query_entity_last_values(self, influx, entities, tzinfo=None, **kwargs):
        """Batch last-value query that never raises; missing keys map to ``None``.

        Only the exceptions understood by the per-entity helper are swallowed; a
        genuine programming error must still surface instead of turning the live
        dashboard into a silent wall of ``None``.
        """
        keys = list((entities or {}).keys())
        try:
            records = self.query_entity_last_values(influx, entities, tzinfo=tzinfo, **kwargs)
        except (HTTPException, requests.RequestException, ValueError, TypeError) as exc:
            self.logger.warning("Batch last-value query failed: %s", exc)
            records = {}
        return {key: records.get(key) for key in keys}

    def query_recent_slot_profile_by_day_type(
        self,
        influx,
        entity_id,
        tzinfo,
        target_date,
        days=28,
        interval="15m",
        measurement_candidates=None,
    ):
        if not entity_id:
            return {}
        
        # Agregujeme průměry po slotech (index 0-95) pro pracovní dny / víkend
        is_weekend = target_date.weekday() >= 5
        
        end_utc = datetime.now(timezone.utc)
        start_utc = end_utc - timedelta(days=days)
        
        points = self.query_entity_series(
            influx,
            entity_id,
            start_utc,
            end_utc,
            interval=interval,
            tzinfo=tzinfo,
            numeric=True,
            measurement_candidates=measurement_candidates
        )
        
        if not points:
            return {}
            
        slots = {} # slot_index -> [values]
        for p in points:
            if p["value"] is None:
                continue
            dt = datetime.fromisoformat(p["time"])
            p_is_weekend = dt.weekday() >= 5
            if p_is_weekend != is_weekend:
                continue
            
            slot = get_slot_index_for_dt(dt)
            slots.setdefault(slot, []).append(p["value"])
            
        return {slot: sum(vals)/len(vals) for slot, vals in slots.items() if vals}
