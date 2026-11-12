from services.data_export_service import DataExportService
from services.billing_service import BillingService
from datetime import datetime, time
from zoneinfo import ZoneInfo


class FakeBillingService:
    def get_invoice_detail_rows(self, cfg, month_str, tzinfo, *, kind):
        return [
            {
                "date": "2026-06-01",
                "interval": "00:00 - 00:14",
                "spot_eur_mwh": 150.14,
                "spot_czk_mwh": 3646.9,
                "effective_eur_mwh": 135.73,
                "effective_czk_mwh": 3296.9,
                "kwh": 0.01,
                "exchange_rate": 24.29,
                "result_eur": 0.0013573,
                "result_czk": 0.032969,
            }
        ]


def test_supply_invoice_detail_csv_matches_supplier_column_order():
    service = DataExportService(FakeBillingService())
    csv_data = service.generate_invoice_detail_csv({}, "2026-06", None, kind="supply")

    lines = csv_data.splitlines()
    assert lines[0] == "Datum;Interval;EUR/MWh;CZK/MWh;Spotřeba kWh;Kurz;EUR;CZK"
    assert lines[1].startswith("2026-06-01;00:00 - 00:14;150,1400;3646,9000;0,01000;24,2900")


def test_export_invoice_detail_csv_matches_supplier_column_order():
    service = DataExportService(FakeBillingService())
    csv_data = service.generate_invoice_detail_csv({}, "2026-06", None, kind="export")

    lines = csv_data.splitlines()
    assert lines[0] == (
        "Datum;Interval;Cena DT OTE EUR/MWh;Cena DT OTE Kč/MWh;Cena výkupu EUR/MWh;"
        "Cena výkupu Kč/MWh;Výkup kWh;Kurz;Výsledná cena EUR;Výsledná cena Kč"
    )
    assert lines[1].startswith("2026-06-01;00:00 - 00:14;150,1400;3646,9000;135,7300;3296,9000")


def test_invoice_breakdown_reconciles_supplier_invoice_totals():
    tzinfo = ZoneInfo("Europe/Prague")

    def consumption(cfg, date=None, start=None, end=None):
        has_data = bool(date and date.startswith("2026-06-"))
        return {
            "tzinfo": tzinfo,
            "has_series": has_data,
            "points": ([
                {"time": "2026-06-01T00:00:00+02:00", "time_utc": "2026-05-31T22:00:00Z", "kwh": 160.69},
                {"time": "2026-06-01T06:00:00+02:00", "time_utc": "2026-06-01T04:00:00Z", "kwh": 24.53},
            ] if date == "2026-06-01" else []),
        }

    fee_snapshot = {
        "dph_percent": 21,
        "kwh_fees": {
            "komodita_sluzba": 0.35,
            "oze": 0,
            "dan": 0.0283,
            "systemove_sluzby": 0.16424,
            "distribuce": {"NT": 0.1165, "VT": 0.75477},
        },
        "fixed": {
            "daily": {"staly_plat": 4.18},
            "monthly": {"jistic": 710, "provoz_nesitove_infrastruktury": 12.87},
        },
        "prodej": {"koeficient_snizeni_ceny": 350},
    }
    spot_kwh = 339.01 / 184.0
    final_kwh = (spot_kwh + 0.35 + 0.0283 + 0.16424 + 0.1165) * 1.21
    price_map = {
        "2026-06-01 00:00": {"spot": spot_kwh, "final": final_kwh},
        "2026-06-01 06:00": {"spot": spot_kwh, "final": (spot_kwh + 0.35 + 0.0283 + 0.16424 + 0.75477) * 1.21},
    }
    service = BillingService(
        get_consumption_points=consumption,
        get_export_points=lambda cfg, date=None, start=None, end=None: {"tzinfo": tzinfo, "has_series": False, "points": []},
        build_price_map_for_date=lambda cfg, date, tz: (price_map, price_map),
        get_export_entity_id=lambda cfg: None,
        get_fee_snapshot_for_date=lambda cfg, date, tz: fee_snapshot,
        compute_fixed_breakdown_for_day=lambda snapshot, days: (
            {"staly_plat": 4.18 * 1.21},
            {"jistic": 710 / days * 1.21, "provoz_nesitove_infrastruktury": 12.87 / days * 1.21},
        ),
        calculate_sell_coefficient=lambda cfg, snapshot: 0.35,
    )

    result = service.compute_monthly_billing({"dph": 21, "tarif": {"vt_periods": [[6, 7]]}}, "2026-06", tzinfo, require_data=False)
    invoice = result["invoice"]["actual"]

    assert invoice["commercial"]["total"] == 528.81
    assert invoice["regulated"]["total"] == 795.05
    assert invoice["supply_without_vat"] == 1323.86
    assert invoice["supply_with_vat"] == 1601.87
    assert invoice["regulated"]["distribution_nt_kwh"] == 160.0
    assert invoice["regulated"]["distribution_vt_kwh"] == 24.0
    assert result["actual"]["kwh_total"] == 185.22
    assert result["invoice"]["billed_quantity_rounding"] == "floor_tariff_kwh"

    partial = service.compute_monthly_billing(
        {"dph": 21, "tarif": {"vt_periods": [[6, 7]]}},
        "2026-06",
        tzinfo,
        require_data=False,
        date_from="2026-06-01",
        date_to="2026-06-01",
        audit_kind="invoice_pdf",
    )
    assert partial["days_with_data"] == 1
    assert partial["invoice"]["actual"]["commercial"]["standing_charge"] == 4.18
    assert partial["invoice"]["actual"]["regulated"]["breaker"] == 23.67
    assert partial["invoice"]["actual"]["regulated"]["infrastructure"] == 0.43


def test_invoice_detail_rows_use_each_historical_fixed_price_mode():
    tzinfo = ZoneInfo("Europe/Prague")
    series = {
        "tzinfo": tzinfo,
        "has_series": True,
        "points": [{
            "time": "2026-11-01T00:00:00+01:00",
            "time_utc": "2026-10-31T23:00:00Z",
            "kwh": 2.0,
        }],
    }
    price = {
        "spot": 2.0,
        "final": 3.0,
        "price_czk_mwh": 2000.0,
        "price_eur_mwh": 80.0,
        "eur_czk_rate": 25.0,
        "purchase_fixed": True,
        "purchase_fixed_price": 5.0,
        "sale_fixed": True,
        "sale_fixed_price": 7.0,
        "export_price": 1.65,
    }
    service = BillingService(
        get_consumption_points=lambda cfg, date=None, start=None, end=None: series,
        get_export_points=lambda cfg, date=None, start=None, end=None: series,
        build_price_map_for_date=lambda cfg, date, tz: ({"2026-11-01 00:00": price}, {"2026-10-31 23:00": price}),
        get_export_entity_id=lambda cfg: "sensor.export",
        get_fee_snapshot_for_date=lambda cfg, date, tz: {
            "dph_percent": 21,
            "nakup": {"fixni_cena_enabled": True, "fixni_cena": 5.0},
            "prodej": {"fixni_cena_enabled": True, "fixni_cena": 7.0},
        },
        compute_fixed_breakdown_for_day=lambda snapshot, days: ({}, {}),
        calculate_sell_coefficient=lambda cfg, snapshot: 0.35,
    )

    supply = service.get_invoice_detail_rows({}, "2026-11", tzinfo, kind="supply")
    export = service.get_invoice_detail_rows({}, "2026-11", tzinfo, kind="export")
    assert supply[0]["spot_czk_mwh"] == 2000.0
    assert supply[0]["effective_czk_mwh"] == 5000.0
    assert export[0]["effective_czk_mwh"] == 7000.0
    assert export[0]["result_czk"] == 14.0


def test_fixed_export_ignores_import_fees_and_sell_coefficient():
    tzinfo = ZoneInfo("Europe/Prague")
    service = BillingService(
        get_consumption_points=lambda cfg, date=None, start=None, end=None: {"tzinfo": tzinfo, "has_series": False, "points": []},
        get_export_points=lambda cfg, date=None, start=None, end=None: {
            "tzinfo": tzinfo,
            "has_series": True,
            "points": [{"time": "2026-11-01T00:00:00+01:00", "time_utc": "2026-10-31T23:00:00Z", "kwh": 3.0}],
        },
        build_price_map_for_date=lambda cfg, date, tz: (
            {"2026-11-01 00:00": {"spot": 2.0}},
            {"2026-10-31 23:00": {"spot": 2.0}},
        ),
        get_export_entity_id=lambda cfg: "sensor.export",
        get_fee_snapshot_for_date=lambda cfg, date, tz: {
            "prodej": {"fixni_cena_enabled": True, "fixni_cena": 5.0},
            "kwh_fees": {"distribuce": {"NT": 100, "VT": 200}},
        },
        compute_fixed_breakdown_for_day=lambda snapshot, days: ({}, {}),
        calculate_sell_coefficient=lambda cfg, snapshot: 0.35,
    )

    result = service.calculate_daily_export_totals({}, "2026-11-01")
    assert result["export_kwh_total"] == 3.0
    assert result["sell_total"] == 15.0


def test_month_projection_uses_future_fixed_price_when_market_series_is_missing():
    tzinfo = ZoneInfo("Europe/Prague")
    today = datetime.now(tzinfo).date()
    month = today.strftime("%Y-%m")
    date_str = today.isoformat()
    consumption = {
        "tzinfo": tzinfo,
        "has_series": True,
        "points": [{
            "time": datetime.combine(today, time.min, tzinfo).isoformat(),
            "time_utc": datetime.combine(today, time.min, tzinfo).astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00", "Z"),
            "kwh": 2.0,
        }],
    }

    def snapshot(cfg, requested_date, tz):
        return {
            "dph_percent": 0,
            "kwh_fees": {"distribuce": {}},
            "fixed": {"daily": {}, "monthly": {}},
            "nakup": {"fixni_cena_enabled": requested_date > date_str, "fixni_cena": 5.0},
            "prodej": {"fixni_cena_enabled": False, "koeficient_snizeni_ceny": 0},
        }

    service = BillingService(
        get_consumption_points=lambda cfg, date=None, start=None, end=None: consumption if date == date_str else {
            "tzinfo": tzinfo, "has_series": False, "points": [],
        },
        get_export_points=lambda cfg, date=None, start=None, end=None: {
            "tzinfo": tzinfo, "has_series": False, "points": [],
        },
        build_price_map_for_date=lambda cfg, requested_date, tz: (
            ({f"{date_str} 00:00": {"spot": 10.0, "final": 10.0}}, {}) if requested_date == date_str else ({}, {})
        ),
        get_export_entity_id=lambda cfg: None,
        get_fee_snapshot_for_date=snapshot,
        compute_fixed_breakdown_for_day=lambda fee, days: ({}, {}),
        calculate_sell_coefficient=lambda cfg, fee: 0.0,
    )

    result = service.compute_monthly_billing(
        {"tarif": {"vt_periods": []}}, month, tzinfo, require_data=False,
    )

    remaining_days = result["days_in_month"] - today.day
    assert result["invoice"]["actual"]["commercial"]["spot_energy"] == 20.0
    assert result["invoice"]["projected"]["commercial"]["spot_energy"] == 20.0 + 2.0 * 5.0 * remaining_days
