import { render, screen } from "@testing-library/react";
import BillingCard from "./BillingCard";
import MonthlySummaryCard from "./MonthlySummaryCard";
import DataCard from "./common/DataCard";

vi.mock("../api/elektroappApi", () => ({
  elektroappApi: {
    exportMonthlyCsv: vi.fn(),
    getInvoiceDetailCsv: vi.fn(),
  },
}));

describe("MonthlySummaryCard", () => {
  test("renders monthly rows and totals", () => {
    const { container } = render(
      <MonthlySummaryCard
        selectedMonth="2026-02"
        setSelectedMonth={() => {}}
        monthlySummary={[
          {
            date: "2026-02-10",
            kwh_total: 12.345,
            pv_kwh: 33.456,
            cost_total: 45.678,
            export_kwh_total: 1.5,
            sell_total: 2.75,
          },
        ]}
        monthlyTotals={{
          kwh_total: 12.345,
          pv_kwh: 33.456,
          cost_total: 45.678,
          export_kwh_total: 1.5,
          sell_total: 2.75,
        }}
        monthlyError={null}
      />
    );

    expect(screen.getByText(/Sou/)).toBeInTheDocument();
    expect(screen.getByText(/Vyrobeno FV \(kWh\)/)).toBeInTheDocument();
    expect(screen.getAllByText("12.35").length).toBeGreaterThan(0);
    expect(screen.getAllByText("33.46").length).toBeGreaterThan(0);
    expect(screen.getAllByText("45.68").length).toBeGreaterThan(0);
    expect(screen.getAllByText("+42.93").length).toBeGreaterThan(0);
    expect(screen.queryByText(/Fixní \(Kč\)/)).not.toBeInTheDocument();
    expect(container.querySelector(".monthly-summary-table-container")).not.toHaveAttribute("style");
  });

  test("renders monthly error state", () => {
    render(
      <DataCard error="Chyba pri nacitani mesicniho souhrnu.">
        <MonthlySummaryCard
          selectedMonth="2026-02"
          setSelectedMonth={() => {}}
          monthlySummary={[]}
          monthlyTotals={null}
          monthlyError="Chyba pri nacitani mesicniho souhrnu."
        />
      </DataCard>
    );

    expect(screen.getByText("Chyba pri nacitani mesicniho souhrnu.")).toBeInTheDocument();
  });

});

describe("BillingCard", () => {
  test("renders loading state", () => {
    render(
      <DataCard loading={true}>
        <BillingCard billingLoading={true} billingMode="month" setBillingMode={() => {}} />
      </DataCard>
    );

    expect(screen.getByText(/Nacitam/)).toBeInTheDocument();
  });

  test("renders error state", () => {
    render(
      <DataCard error="Nepodarilo se nacist vyuctovani.">
        <BillingCard billingError="Nepodarilo se nacist vyuctovani." billingMode="month" setBillingMode={() => {}} />
      </DataCard>
    );

    expect(screen.getByText("Nepodarilo se nacist vyuctovani.")).toBeInTheDocument();
  });

  test("renders settlement estimate in billing card", () => {
    render(
      <BillingCard
        billingMode="month"
        setBillingMode={() => {}}
        billingMonth="2026-07"
        setBillingMonth={() => {}}
        billingYear="2026"
        setBillingYear={() => {}}
        maxMonth="2026-07"
        maxYear="2026"
        billingData={{
          month: "2026-07",
          days_with_data: 14,
          days_in_month: 31,
          actual: { kwh_total: 58.17, variable_cost: 142.45, fixed_cost: 1031.46, sell_total: 189.47, net_total: 984.45 },
          projected: { net_total: 927.35 },
          monthly_advance: 2500,
          settlement_estimate: 1572.65,
          invoice: {
            dph_percent: 21,
            price_provider: "ote",
            projected: {
              commercial: { standing_charge: 125.4, supplier_service: 64.4, spot_energy: 339.01, total: 528.81 },
              regulated: {
                distribution_nt_kwh: 160,
                distribution_nt: 18.64,
                distribution_vt_kwh: 24,
                distribution_vt: 18.11,
                breaker: 710,
                infrastructure: 12.87,
                oze: 0,
                electricity_tax: 5.21,
                system_services: 30.22,
                total: 795.05,
              },
              supply_without_vat: 1323.86,
              supply_with_vat: 1601.87,
              sell_total: 598.41,
              net_after_sell: 1003.46,
            },
          },
        }}
      />
    );

    expect(screen.getByText(/Odhad vratky/)).toBeInTheDocument();
    expect(screen.getByText(/Záloha 2 500 Kč/)).toBeInTheDocument();
    expect(screen.getByText("Obchodní platby")).toBeInTheDocument();
    expect(screen.getByText("Regulované platby")).toBeInTheDocument();
    expect(screen.getByText("Výsledek vyúčtování")).toBeInTheDocument();
  });
});
