from services.data_export_service import DataExportService
from services.billing_service import BillingService
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
        has_data = date == "2026-06-01"
        return {
            "tzinfo": tzinfo,
            "has_series": has_data,
            "points": ([
                {"time": "2026-06-01T00:00:00+02:00", "time_utc": "2026-05-31T22:00:00Z", "kwh": 160.0},
                {"time": "2026-06-01T06:00:00+02:00", "time_utc": "2026-06-01T04:00:00Z", "kwh": 24.0},
            ] if has_data else []),
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
