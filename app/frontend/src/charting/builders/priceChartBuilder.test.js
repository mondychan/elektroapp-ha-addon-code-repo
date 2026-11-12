import { describe, expect, it } from "vitest";
import { buildPriceChartConfig } from "./priceChartBuilder";

describe("buildPriceChartConfig", () => {
  it("keeps a fixed purchase price in the fixed series when spot is negative", () => {
    const config = buildPriceChartConfig({
      chartData: [{ slot: 0, spot: -1.5, extra: 7.9, final: 6.4 }],
      vtPeriods: [],
      fixedPriceMode: true,
    });

    expect(config.data.datasets.map((dataset) => dataset.data[0])).toEqual([6.4, null, null]);
  });

  it("keeps fixed charges separate from a fixed commodity price", () => {
    const config = buildPriceChartConfig({
      chartData: [{ slot: 0, spot: 0, extra: 6.4, final: 6.4 }],
      vtPeriods: [],
      fixedPriceMode: true,
    });

    expect(config.data.datasets.map((dataset) => dataset.data[0])).toEqual([6.4, null, null]);
  });

  it("uses each point's historical purchase mode", () => {
    const config = buildPriceChartConfig({
      chartData: [
        { slot: 0, spot: 4, extra: 2, final: 6, purchase_fixed: true },
        { slot: 1, spot: 4, extra: 2, final: 6, purchase_fixed: false },
      ],
      vtPeriods: [],
      fixedPriceMode: true,
    });

    expect(config.data.datasets.map((dataset) => dataset.data)).toEqual([
      [6, 2],
      [null, null],
      [null, 4],
    ]);
  });
});
