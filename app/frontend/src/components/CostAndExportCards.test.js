import { render, screen } from "@testing-library/react";
import CostChartCard from "./CostChartCard";
import ExportChartCard from "./ExportChartCard";
import { buildCostChartData, buildExportChartData } from "../charting/builders/costExportBuilder";

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

  test("fills missing cost slots with zero values", () => {
    const chartData = buildCostChartData([
      { time: "2026-03-08T00:15:00+01:00", kwh: 0.18, cost: 0.34 },
      { time: "2026-03-08T00:45:00+01:00", kwh: null, cost: null },
    ]);

    expect(chartData[0]).toEqual({ slot: 0, time: "00:00", kwh: 0, cost: 0 });
    expect(chartData[1]).toEqual({ slot: 1, time: "00:15", kwh: 0.18, cost: 0.34 });
    expect(chartData[2]).toEqual({ slot: 2, time: "00:30", kwh: 0, cost: 0 });
    expect(chartData[3]).toEqual({ slot: 3, time: "00:45", kwh: 0, cost: 0 });
  });

  test("fills missing export slots with zero values", () => {
    const chartData = buildExportChartData([
      { time: "2026-03-08T11:00:00+01:00", kwh: 0.25, sell: 0.41 },
      { time: "2026-03-08T11:15:00+01:00", kwh: null, sell: null },
    ]);

    expect(chartData[44]).toEqual({ slot: 44, time: "11:00", kwh: 0.25, sell: 0.41 });
    expect(chartData[45]).toEqual({ slot: 45, time: "11:15", kwh: 0, sell: 0 });
    expect(chartData[46]).toEqual({ slot: 46, time: "11:30", kwh: 0, sell: 0 });
  });
});
