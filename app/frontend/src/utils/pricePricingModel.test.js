import { describe, expect, it } from "vitest";
import { buildTomorrowChartPlan, hasDifferingPricingModels, hasDynamicPrice } from "./pricePricingModel.js";

const point = (overrides = {}) => ({
  slot: 0,
  time: "00:00",
  spot: 2,
  extra: 0,
  final: 2,
  exportPrice: 2,
  ...overrides,
});

describe("hasDifferingPricingModels", () => {
  it("returns false for empty data", () => {
    expect(hasDifferingPricingModels([])).toBe(false);
    expect(hasDifferingPricingModels(undefined)).toBe(false);
  });

  it("returns false when both directions are spot", () => {
    const data = [
      point({ spot: 2.0, extra: 0.5, final: 2.5, exportPrice: 2.0, purchase_fixed: false, sale_fixed: false }),
      point({ slot: 1, spot: -1.0, extra: 0.5, final: -0.5, exportPrice: -1.0, purchase_fixed: false, sale_fixed: false }),
    ];
    expect(hasDifferingPricingModels(data)).toBe(false);
  });

  it("keeps one chart when both directions are fixed even at different rates", () => {
    const data = [
      point({ final: 7.35, purchase_fixed: true, sale_fixed: true, exportPrice: 5.0 }),
    ];
    expect(hasDifferingPricingModels(data)).toBe(false);
  });

  it("splits when purchase is fixed and export is spot", () => {
    expect(
      hasDifferingPricingModels([point({ final: 7.35, purchase_fixed: true, sale_fixed: false, exportPrice: 2 })])
    ).toBe(true);
  });

  it("splits when purchase is spot and export is fixed", () => {
    expect(
      hasDifferingPricingModels([point({ final: 2, purchase_fixed: false, sale_fixed: true, exportPrice: 5 })])
    ).toBe(true);
  });

  it("does not split on raw value differences when flags agree", () => {
    const data = [point({ final: 7.35, purchase_fixed: true, sale_fixed: true, exportPrice: 5.0 })];
    expect(hasDifferingPricingModels(data)).toBe(false);
  });

  it("does not split legacy payloads without flags", () => {
    const data = [point({ final: 2.5, exportPrice: 2.0 }), point({ slot: 1, final: -0.5, exportPrice: -1.0 })];
    expect(hasDifferingPricingModels(data)).toBe(false);
  });

  it("uses day-level defaults when points omit flags", () => {
    const data = [point({ final: 7.35, exportPrice: 2.0 })];
    expect(hasDifferingPricingModels(data, { purchaseFixed: true, saleFixed: false })).toBe(true);
    expect(hasDifferingPricingModels(data, { purchaseFixed: true, saleFixed: true })).toBe(false);
  });

  it("ignores points without any usable flag", () => {
    expect(hasDifferingPricingModels([null, undefined, {}])).toBe(false);
  });
});

describe("hasDynamicPrice", () => {
  it("treats fixed purchase + spot sale as a dynamic sale day", () => {
    const data = [point({ purchase_fixed: true, sale_fixed: false })];
    expect(hasDynamicPrice(data, "purchase", true)).toBe(false);
    expect(hasDynamicPrice(data, "sale", true)).toBe(true);
  });

  it("returns false when the whole day is fixed in that direction", () => {
    const data = [point({ purchase_fixed: true, sale_fixed: true }), point({ slot: 1, purchase_fixed: true, sale_fixed: true })];
    expect(hasDynamicPrice(data, "purchase", false)).toBe(false);
    expect(hasDynamicPrice(data, "sale", false)).toBe(false);
  });

  it("falls back to the configuration for legacy payloads", () => {
    expect(hasDynamicPrice([point({})], "purchase", false)).toBe(true);
    expect(hasDynamicPrice([point({})], "purchase", true)).toBe(false);
    expect(hasDynamicPrice([point({})], "sale", true)).toBe(false);
  });

  it("returns false for non-arrays", () => {
    expect(hasDynamicPrice(undefined, "sale", false)).toBe(false);
    expect(hasDynamicPrice(null, "purchase", false)).toBe(false);
  });
});

describe("buildTomorrowChartPlan", () => {
  const fixedPurchaseSpotSale = [
    point({ purchase_fixed: true, sale_fixed: false, final: 7.35, exportPrice: 2.0 }),
  ];

  it("shows the tomorrow export chart for fixed purchase + spot sale", () => {
    expect(
      buildTomorrowChartPlan({
        tomorrowPoints: fixedPurchaseSpotSale,
        purchaseFixed: true,
        saleFixed: false,
        separateTomorrowExportPrice: true,
      }),
    ).toEqual({ showPurchaseChart: false, showExportChart: true });
  });

  it("hides the redundant tomorrow purchase chart when purchase is fixed", () => {
    // Fixed purchase repeats today's shape, so there is nothing to compare.
    expect(
      buildTomorrowChartPlan({
        tomorrowPoints: fixedPurchaseSpotSale,
        purchaseFixed: true,
        saleFixed: false,
        separateTomorrowExportPrice: false,
      }),
    ).toEqual({ showPurchaseChart: false, showExportChart: false });
  });

  it("does not show the export chart when both directions are dynamic", () => {
    const spotBoth = [point({ purchase_fixed: false, sale_fixed: false })];
    expect(
      buildTomorrowChartPlan({
        tomorrowPoints: spotBoth,
        purchaseFixed: false,
        saleFixed: false,
        separateTomorrowExportPrice: false,
      }),
    ).toEqual({ showPurchaseChart: true, showExportChart: false });
  });

  it("shows the purchase chart when tomorrow has spot purchase prices", () => {
    const spotPurchase = [point({ purchase_fixed: false, sale_fixed: false })];
    expect(
      buildTomorrowChartPlan({
        tomorrowPoints: spotPurchase,
        purchaseFixed: false,
        saleFixed: false,
        separateTomorrowExportPrice: true,
      }),
    ).toEqual({ showPurchaseChart: true, showExportChart: true });
  });

  it("renders nothing without tomorrow data", () => {
    expect(
      buildTomorrowChartPlan({
        tomorrowPoints: [],
        purchaseFixed: false,
        saleFixed: false,
        separateTomorrowExportPrice: true,
      }),
    ).toEqual({ showPurchaseChart: false, showExportChart: false });
    expect(buildTomorrowChartPlan()).toEqual({ showPurchaseChart: false, showExportChart: false });
  });
});
