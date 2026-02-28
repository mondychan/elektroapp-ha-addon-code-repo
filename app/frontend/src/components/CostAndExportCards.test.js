import { render, screen } from "@testing-library/react";
import CostChartCard from "./CostChartCard";
import ExportChartCard from "./ExportChartCard";

describe("Cost and Export cards", () => {
  test("shows cost API error", () => {
    render(
      <CostChartCard
        selectedDate="2026-02-28"
        setSelectedDate={() => {}}
        costs={[]}
        costsSummary={null}
        costsError="Nepodarilo se pripojit k InfluxDB."
        costsFromCache={false}
        costsCacheFallback={false}
      />
    );

    expect(screen.getByText("Nepodarilo se pripojit k InfluxDB.")).toBeInTheDocument();
  });

  test("shows export API error", () => {
    render(
      <ExportChartCard
        selectedDate="2026-02-28"
        setSelectedDate={() => {}}
        exportPoints={[]}
        exportSummary={null}
        exportError="Chyba pri nacitani z InfluxDB (HTTP 500)."
        exportFromCache={false}
        exportCacheFallback={false}
      />
    );

    expect(screen.getByText("Chyba pri nacitani z InfluxDB (HTTP 500).")).toBeInTheDocument();
  });
});
