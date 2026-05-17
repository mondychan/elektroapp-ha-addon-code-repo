import { render, screen } from "@testing-library/react";
import { describe, expect, test } from "vitest";
import DailySummaryCard, { getSummaryTone } from "./DailySummaryCard";

describe("DailySummaryCard", () => {
  test("classifies cost, gain, and net values by meaning", () => {
    expect(getSummaryTone("cost", 12)).toBe("cost");
    expect(getSummaryTone("gain", 8)).toBe("gain");
    expect(getSummaryTone("net", -2)).toBe("net-positive");
    expect(getSummaryTone("net", 2)).toBe("net-negative");
    expect(getSummaryTone("net", 0)).toBe("net-zero");
  });

  test("renders colored rows for import, export, and net", () => {
    render(
      <DailySummaryCard
        costsSummary={{ kwh_total: 3.67, cost_total: 3.17 }}
        exportSummary={{ export_kwh_total: 0.4, sell_total: 0.78 }}
        batteryData={{ current_energy: { house_load_w: 12390 } }}
        solarForecast={{ actual: { production_today_kwh: 13.51 } }}
      />
    );

    expect(screen.getByText("Import ze sítě").closest("tr")!).toHaveClass("daily-summary__row--cost");
    expect(screen.getByText("Export do sítě").closest("tr")!).toHaveClass("daily-summary__row--gain");
    expect(screen.getByText("Netto").closest("tr")!).toHaveClass("daily-summary__row--net-negative");
  });
});
