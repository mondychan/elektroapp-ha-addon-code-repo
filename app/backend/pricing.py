import re
from html.parser import HTMLParser


PRICE_PROVIDER_SPOT = "spotovaelektrina"
PRICE_PROVIDER_OTE = "ote"
DEFAULT_PRICE_PROVIDER = PRICE_PROVIDER_SPOT


def parse_vt_periods(value):
    if isinstance(value, list):
        return value
    if not isinstance(value, str):
        return []
    periods = []
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" not in part:
            continue
        start_str, end_str = part.split("-", 1)
        try:
            start = int(start_str.strip())
            end = int(end_str.strip())
        except ValueError:
            continue
        periods.append([start, end])
    return periods


def normalize_price_provider(value):
    if not isinstance(value, str):
        return DEFAULT_PRICE_PROVIDER
    normalized = value.strip().lower()
    if normalized in {PRICE_PROVIDER_SPOT, "spotovaelektrina.cz", "spot"}:
        return PRICE_PROVIDER_SPOT
    if normalized in {PRICE_PROVIDER_OTE, "ote-cr.cz", "ote.cz", "otecr"}:
        return PRICE_PROVIDER_OTE
    return DEFAULT_PRICE_PROVIDER


def get_price_provider(cfg):
    if not isinstance(cfg, dict):
        return DEFAULT_PRICE_PROVIDER
    return normalize_price_provider(cfg.get("price_provider"))


def _safe_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_dph_percent(value):
    dph_value = _safe_float(value)
    if dph_value <= 0:
        return 0.0
    if dph_value <= 2:
        return max(0.0, (dph_value - 1) * 100)
    return dph_value


def build_fee_snapshot(cfg):
    poplatky = cfg.get("poplatky", {}) if isinstance(cfg.get("poplatky"), dict) else {}
    distribuce = poplatky.get("distribuce", {}) if isinstance(poplatky.get("distribuce"), dict) else {}
    fixni = cfg.get("fixni", {}) if isinstance(cfg.get("fixni"), dict) else {}
    fixni_denni = fixni.get("denni", {}) if isinstance(fixni.get("denni"), dict) else {}
    fixni_mesicni = fixni.get("mesicni", {}) if isinstance(fixni.get("mesicni"), dict) else {}
    prodej = cfg.get("prodej", {}) if isinstance(cfg.get("prodej"), dict) else {}
    oze_value = poplatky.get("oze")
    if oze_value is None:
        oze_value = poplatky.get("poze", 0)
    return {
        "dph_percent": normalize_dph_percent(cfg.get("dph", 0)),
        "kwh_fees": {
            "komodita_sluzba": _safe_float(poplatky.get("komodita_sluzba", 0)),
            "oze": _safe_float(oze_value),
            "dan": _safe_float(poplatky.get("dan", 0)),
            "systemove_sluzby": _safe_float(poplatky.get("systemove_sluzby", 0)),
            "distribuce": {
                "NT": _safe_float(distribuce.get("NT", 0)),
                "VT": _safe_float(distribuce.get("VT", 0)),
            },
        },
        "fixed": {
            "daily": {
                "staly_plat": _safe_float(fixni_denni.get("staly_plat", 0)),
            },
            "monthly": {
                "provoz_nesitove_infrastruktury": _safe_float(
                    fixni_mesicni.get("provoz_nesitove_infrastruktury", 0)
                ),
                "jistic": _safe_float(fixni_mesicni.get("jistic", 0)),
            },
        },
        "prodej": {
            "koeficient_snizeni_ceny": _safe_float(prodej.get("koeficient_snizeni_ceny", 0)),
        },
    }


def normalize_fee_snapshot(snapshot):
    if not isinstance(snapshot, dict):
        snapshot = {}

    if "kwh_fees" in snapshot or "fixed" in snapshot:
        kwh_fees = snapshot.get("kwh_fees", {}) if isinstance(snapshot.get("kwh_fees"), dict) else {}
        distribuce = kwh_fees.get("distribuce", {}) if isinstance(kwh_fees.get("distribuce"), dict) else {}
        fixed = snapshot.get("fixed", {}) if isinstance(snapshot.get("fixed"), dict) else {}
        daily = fixed.get("daily", {}) if isinstance(fixed.get("daily"), dict) else {}
        monthly = fixed.get("monthly", {}) if isinstance(fixed.get("monthly"), dict) else {}
        prodej = snapshot.get("prodej", {}) if isinstance(snapshot.get("prodej"), dict) else {}
        return {
            "dph_percent": normalize_dph_percent(snapshot.get("dph_percent", snapshot.get("dph", 0))),
            "kwh_fees": {
                "komodita_sluzba": _safe_float(kwh_fees.get("komodita_sluzba", 0)),
                "oze": _safe_float(kwh_fees.get("oze", 0)),
                "dan": _safe_float(kwh_fees.get("dan", 0)),
                "systemove_sluzby": _safe_float(kwh_fees.get("systemove_sluzby", 0)),
                "distribuce": {
                    "NT": _safe_float(distribuce.get("NT", 0)),
                    "VT": _safe_float(distribuce.get("VT", 0)),
                },
            },
            "fixed": {
                "daily": {
                    "staly_plat": _safe_float(daily.get("staly_plat", 0)),
                },
                "monthly": {
                    "provoz_nesitove_infrastruktury": _safe_float(
                        monthly.get("provoz_nesitove_infrastruktury", 0)
                    ),
                    "jistic": _safe_float(monthly.get("jistic", 0)),
                },
            },
            "prodej": {
                "koeficient_snizeni_ceny": _safe_float(
                    prodej.get("koeficient_snizeni_ceny", snapshot.get("koeficient_snizeni_ceny", 0))
                ),
            },
        }

    poplatky = snapshot.get("poplatky", {}) if isinstance(snapshot.get("poplatky"), dict) else {}
    distribuce = poplatky.get("distribuce", {}) if isinstance(poplatky.get("distribuce"), dict) else {}
    fixni = snapshot.get("fixni", {}) if isinstance(snapshot.get("fixni"), dict) else {}
    fixni_denni = fixni.get("denni", {}) if isinstance(fixni.get("denni"), dict) else {}
    fixni_mesicni = fixni.get("mesicni", {}) if isinstance(fixni.get("mesicni"), dict) else {}
    prodej = snapshot.get("prodej", {}) if isinstance(snapshot.get("prodej"), dict) else {}
    oze_value = poplatky.get("oze")
    if oze_value is None:
        oze_value = poplatky.get("poze", 0)
    return {
        "dph_percent": normalize_dph_percent(snapshot.get("dph", 0)),
        "kwh_fees": {
            "komodita_sluzba": _safe_float(poplatky.get("komodita_sluzba", 0)),
            "oze": _safe_float(oze_value),
            "dan": _safe_float(poplatky.get("dan", 0)),
            "systemove_sluzby": _safe_float(poplatky.get("systemove_sluzby", 0)),
            "distribuce": {
                "NT": _safe_float(distribuce.get("NT", 0)),
                "VT": _safe_float(distribuce.get("VT", 0)),
            },
        },
        "fixed": {
            "daily": {
                "staly_plat": _safe_float(fixni_denni.get("staly_plat", 0)),
            },
            "monthly": {
                "provoz_nesitove_infrastruktury": _safe_float(
                    fixni_mesicni.get("provoz_nesitove_infrastruktury", 0)
                ),
                "jistic": _safe_float(fixni_mesicni.get("jistic", 0)),
            },
        },
        "prodej": {
            "koeficient_snizeni_ceny": _safe_float(prodej.get("koeficient_snizeni_ceny", 0)),
        },
    }


def calculate_final_price(price_spot_czk, hour, cfg, fee_snapshot):
    vt_periods = cfg.get("tarif", {}).get("vt_periods", [])
    is_vt = any(start <= hour < end for start, end in vt_periods)
    tarif_type = "VT" if is_vt else "NT"
    fees = fee_snapshot.get("kwh_fees", {})
    distribuce = fees.get("distribuce", {})
    subtotal = (
        price_spot_czk
        + fees.get("komodita_sluzba", 0)
        + fees.get("oze", 0)
        + fees.get("dan", 0)
        + fees.get("systemove_sluzby", 0)
        + distribuce.get(tarif_type, 0)
    )
    dph_multiplier = 1 + (fee_snapshot.get("dph_percent", 0) / 100.0)
    total = subtotal * dph_multiplier
    return round(total, 5)


class PriceTableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_td = False
        self.row = []
        self.rows = []
        self._current_data = []

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            attrs_dict = dict(attrs)
            if attrs_dict.get("id") == "prices":
                self.in_table = True
        if self.in_table and tag == "td":
            self.in_td = True
            self._current_data = []

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table = False
        if self.in_table and tag == "td":
            self.in_td = False
            cell = "".join(self._current_data).strip()
            self.row.append(cell)
        if self.in_table and tag == "tr":
            if self.row:
                self.rows.append(self.row)
            self.row = []

    def handle_data(self, data):
        if self.in_td:
            self._current_data.append(data)


def parse_price_html(html_text):
    parser = PriceTableParser()
    parser.feed(html_text)
    rows = []
    for row in parser.rows:
        if len(row) < 2:
            continue
        time_str = row[0]
        price_text = row[1]
        # Historical HTML may contain locale formatting and unicode minus.
        normalized_price = str(price_text).replace("\xa0", " ")
        m = re.search(r"([\-â’â€“â€”ďąŁďĽŤ]?\s*\d[\d\s]*(?:[.,]\d+)?)", normalized_price)
        if not m:
            continue
        raw_number = (
            m.group(1)
            .replace(" ", "")
            .replace("â’", "-")
            .replace("â€“", "-")
            .replace("â€”", "-")
            .replace("ďąŁ", "-")
            .replace("ďĽŤ", "-")
        )
        if not raw_number:
            continue
        # Support both 1 234,56 and 1,234.56 formats.
        if "," in raw_number and "." in raw_number:
            if raw_number.rfind(",") > raw_number.rfind("."):
                raw_number = raw_number.replace(".", "").replace(",", ".")
            else:
                raw_number = raw_number.replace(",", "")
        else:
            raw_number = raw_number.replace(",", ".")
        try:
            price_czk = float(raw_number)
        except ValueError:
            continue
        rows.append((time_str, price_czk))
    return rows
