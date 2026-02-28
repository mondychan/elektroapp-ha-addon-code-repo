import re


def build_influx_from_clause(influx):
    rp = influx.get("retention_policy")
    measurement = influx["measurement"]
    return f'"{measurement}"' if not rp else f'"{rp}"."{measurement}"'


def build_influx_from_clause_for_measurement(influx, measurement):
    rp = influx.get("retention_policy")
    return f'"{measurement}"' if not rp else f'"{rp}"."{measurement}"'


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
