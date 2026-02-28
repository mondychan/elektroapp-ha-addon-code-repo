import { render, screen } from "@testing-library/react";
import BillingCard from "./BillingCard";
import MonthlySummaryCard from "./MonthlySummaryCard";

describe("MonthlySummaryCard", () => {
  test("renders monthly rows and totals", () => {
    render(
      <MonthlySummaryCard
        selectedMonth="2026-02"
        setSelectedMonth={() => {}}
        monthlySummary={[
          {
            date: "2026-02-10",
            kwh_total: 12.345,
            cost_total: 45.678,
            export_kwh_total: 1.5,
            sell_total: 2.75,
          },
        ]}
        monthlyTotals={{
          kwh_total: 12.345,
          cost_total: 45.678,
          export_kwh_total: 1.5,
          sell_total: 2.75,
        }}
        monthlyError={null}
      />
    );

    expect(screen.getByText("Soucet")).toBeInTheDocument();
    expect(screen.getAllByText("12.35").length).toBeGreaterThan(0);
    expect(screen.getAllByText("45.68").length).toBeGreaterThan(0);
  });

  test("renders monthly error state", () => {
    render(
      <MonthlySummaryCard
        selectedMonth="2026-02"
        setSelectedMonth={() => {}}
        monthlySummary={[]}
        monthlyTotals={null}
        monthlyError="Chyba pri nacitani mesicniho souhrnu."
      />
    );

    expect(screen.getByText("Chyba pri nacitani mesicniho souhrnu.")).toBeInTheDocument();
  });
});

describe("BillingCard", () => {
  test("renders loading and error API states", () => {
    render(
      <BillingCard
        billingMode="month"
        setBillingMode={() => {}}
        billingMonth="2026-02"
        setBillingMonth={() => {}}
        billingYear="2026"
        setBillingYear={() => {}}
        billingData={null}
        billingLoading={true}
        billingError="Nepodarilo se nacist vyuctovani."
      />
    );

    expect(screen.getByText("Nepodarilo se nacist vyuctovani.")).toBeInTheDocument();
    expect(screen.getByText("Pocitam odhad vyuctovani...")).toBeInTheDocument();
  });
});
