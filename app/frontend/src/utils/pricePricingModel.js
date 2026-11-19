// Decide whether the purchase (import) and export (sale) charts represent
// different pricing models and therefore deserve separate charts.
//
// The two series are not on the same scale: `final` is the all-in purchase price
// (commodity + fees + distribution + VAT) while the sale price is bare (no fees
// and no VAT). Comparing those values directly would always report a difference
// for a spot purchase with any regulation, even when both directions are spot
// priced. Compare the pricing models instead; the backend decorates every entry
// with the historical fee snapshot flags `purchase_fixed` and `sale_fixed`.
//
// Rules:
//   * fixed purchase + fixed sale, or spot purchase + spot sale: one chart,
//   * fixed purchase + spot sale, or spot purchase + fixed sale: two charts,
//   * legacy payloads without flags keep one chart, so the UI never splits just
//     because the all-in purchase price happens to differ from the sale price.

const readFlag = (value) => {
  if (value == null) return null;
  return Boolean(value);
};

/**
 * Returns true when the purchase and sale directions use different pricing models.
 *
 * @param {Array<Record<string, any>>} [points] price entries for a day
 * @param {{ purchaseFixed?: boolean | null, saleFixed?: boolean | null }} [defaults]
 *   day-level fallback flags for legacy payloads that omit per-point flags
 */
export const hasDifferingPricingModels = (points = [], defaults = {}) => {
  if (!Array.isArray(points) || points.length === 0) return false;

  const fallbackPurchase = readFlag(defaults?.purchaseFixed);
  const fallbackSale = readFlag(defaults?.saleFixed);

  for (const point of points) {
    if (!point) continue;
    const purchaseFixed = readFlag(point.purchase_fixed) ?? fallbackPurchase;
    const saleFixed = readFlag(point.sale_fixed) ?? fallbackSale;
    if (purchaseFixed == null || saleFixed == null) continue;
    if (purchaseFixed !== saleFixed) return true;
  }
  return false;
};

/**
 * True when at least one point of the day uses a dynamic (spot-derived) price
 * for the given direction.  Per-point flags win; `fallback` describes the
 * current configuration and covers legacy payloads that omit the flags.
 *
 * A direction that is fixed for the whole day has the same shape tomorrow, so
 * rendering a "tomorrow" chart for it is redundant.
 *
 * @param {Array<Record<string, any>>} [points]
 * @param {"purchase" | "sale"} direction
 * @param {boolean} [fallback]
 */
export const hasDynamicPrice = (points, direction, fallback = false) => {
  if (!Array.isArray(points)) return false;
  const key = direction === "sale" ? "sale_fixed" : "purchase_fixed";
  return points.some((point) => {
    if (!point) return false;
    const flag = readFlag(point[key]) ?? fallback;
    return !flag;
  });
};

/**
 * Decide which "tomorrow" charts the overview should render.
 *
 * Only a direction whose price actually changes from today to tomorrow earns a
 * chart: a fixed purchase tariff makes tomorrow redundant, while a dynamic sale
 * price is exactly what the user wants to see when purchase is fixed.  That
 * asymmetry is the bug this helper pins down -- the export chart used to be
 * gated on "tomorrow differs from today" (which is false when sale is *fixed*)
 * and the purchase chart was implied by the split itself.
 *
 * @param {{
 *   tomorrowPoints?: Array<Record<string, any>>,
 *   purchaseFixed?: boolean,
 *   saleFixed?: boolean,
 *   separateTomorrowExportPrice?: boolean
 * }} params
 * @returns {{ showPurchaseChart: boolean, showExportChart: boolean }}
 */
export const buildTomorrowChartPlan = ({
  tomorrowPoints = [],
  purchaseFixed = false,
  saleFixed = false,
  separateTomorrowExportPrice = false,
} = {}) => {
  const hasData = Array.isArray(tomorrowPoints) && tomorrowPoints.length > 0;
  if (!hasData) {
    return { showPurchaseChart: false, showExportChart: false };
  }
  const splitCharts = Boolean(separateTomorrowExportPrice);
  return {
    showPurchaseChart: hasDynamicPrice(tomorrowPoints, "purchase", Boolean(purchaseFixed)),
    showExportChart:
      splitCharts && hasDynamicPrice(tomorrowPoints, "sale", Boolean(saleFixed)),
  };
};

export default hasDifferingPricingModels;
