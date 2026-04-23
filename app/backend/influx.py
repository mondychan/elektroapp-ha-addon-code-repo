import re


_INTERVAL_RE = re.compile(r"^\d+[smhdw]$")
_AGGREGATE_FUNCTIONS = {"last", "mean", "min", "max", "sum"}


def escape_influx_identifier(value):
    raw = str(value or "")
    return raw.replace("\\", "\\\\").replace('"', '\\"')


def quote_influx_identifier(value):
    return f'"{escape_influx_identifier(value)}"'


def escape_influx_tag_value(value):
    raw = str(value or "")
    return raw.replace("\\", "\\\\").replace("'", "\\'")


def validate_influx_interval(interval_value, default="15m"):
    raw = str(interval_value or default).strip().lower()
    return raw if _INTERVAL_RE.fullmatch(raw) else default


def validate_influx_aggregate(value, default="last"):
    raw = str(value or default).strip().lower()
    return raw if raw in _AGGREGATE_FUNCTIONS else default


def build_influx_from_clause(influx):
    rp = influx.get("retention_policy")
    measurement = influx["measurement"]
    return quote_influx_identifier(measurement) if not rp else f'{quote_influx_identifier(rp)}.{quote_influx_identifier(measurement)}'


def build_influx_from_clause_for_measurement(influx, measurement):
    rp = influx.get("retention_policy")
    return quote_influx_identifier(measurement) if not rp else f'{quote_influx_identifier(rp)}.{quote_influx_identifier(measurement)}'


def parse_influx_interval_to_minutes(interval_value, default_minutes=15):
    if not isinstance(interval_value, str):
        return default_minutes
    value = interval_value.strip().lower()
    m = re.fullmatch(r"(\d+)([smhd])", value)
    if not m:
        return default_minutes
    amount = int(m.group(1))
    unit = m.group(2)
    if amount <= 0:
        return default_minutes
    if unit == "s":
        return max(1, amount // 60) if amount >= 60 else 1
    if unit == "m":
        return amount
    if unit == "h":
        return amount * 60
    if unit == "d":
        return amount * 1440
    return default_minutes
