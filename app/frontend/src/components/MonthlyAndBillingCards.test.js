import { render, screen } from "@testing-library/react";
import BillingCard from "./BillingCard";
import MonthlySummaryCard from "./MonthlySummaryCard";
import DataCard from "./common/DataCard";

jest.mock("../api/elektroappApi", () => ({
  elektroappApi: {
    exportMonthlyCsv: jest.fn(),
  },
}));

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

    expect(screen.getByText(/Sou/)).toBeInTheDocument();
    expect(screen.getAllByText("12.35").length).toBeGreaterThan(0);
    expect(screen.getAllByText("45.68").length).toBeGreaterThan(0);
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
});
