def test_parse_vt_periods_from_string(backend_main):
    assert backend_main.parse_vt_periods("6-7,9-10,13-14") == [[6, 7], [9, 10], [13, 14]]


def test_parse_vt_periods_ignores_invalid_parts(backend_main):
    assert backend_main.parse_vt_periods("bad,1-2,3-x") == [[1, 2]]


def test_normalize_price_provider_aliases(backend_main):
    assert backend_main.normalize_price_provider("spotovaelektrina.cz") == "spotovaelektrina"
    assert backend_main.normalize_price_provider("ote-cr.cz") == "ote"
    assert backend_main.normalize_price_provider("unknown") == "spotovaelektrina"


def test_parse_influx_interval_to_minutes(backend_main):
    assert backend_main.parse_influx_interval_to_minutes("15m") == 15
    assert backend_main.parse_influx_interval_to_minutes("2h") == 120
    assert backend_main.parse_influx_interval_to_minutes("invalid", default_minutes=30) == 30
