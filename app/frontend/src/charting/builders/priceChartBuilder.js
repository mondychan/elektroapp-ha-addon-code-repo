import { formatSlotToTime } from "../../utils/formatters";
import { buildCurrentSlotAnnotations } from "../plugins/currentSlotPlugin";
import { buildTimeBandAnnotations } from "../plugins/timeBandPlugin";
import { buildThresholdAnnotations } from "../plugins/thresholdPlugin";
import { buildCategoryTimeAxis, buildLinearAxis, buildStaticTimeLabels, buildTooltip, colorScale } from "./common";
import { getChartTheme } from "../chartTheme";

const getVTStatus = (slot, vtPeriods) =>
  (vtPeriods || []).some(([start, end]) => slot >= start * 4 && slot < end * 4) ? "VT" : "NT";

const buildVtBands = (vtPeriods = []) =>
  vtPeriods.map(([start, end]) => ({
    startSlot: start * 4 - 0.5,
    endSlot: end * 4 - 0.5,
    tone: "vt",
  }));

export const buildPriceChartConfig = ({
  chartData,
  title,
  vtPeriods,
  highlightSlot,
  pinnedSlot,
  fallbackMessage,
  thresholds = null,
  fixedPriceMode = false,
  chartMode = "purchase",
}) => {
  if (!chartData?.length) {
    return {
      emptyMessage: fallbackMessage,
      pointPayloads: [],
    };
  }

  const minFinal = Math.min(...chartData.map((item) => item.final));
  const maxFinal = Math.max(...chartData.map((item) => item.final));
  const activeSlot = Number.isInteger(pinnedSlot) ? pinnedSlot : highlightSlot;
  const theme = getChartTheme();
  const fixedColor = theme.accent2 || "rgba(45, 127, 249, 0.9)";
  const coveredNegativeColor = theme.accentAmber || "rgba(245, 158, 11, 0.9)";
  const variableColor = theme.accentRed || "rgba(239, 68, 68, 0.88)";
  const negativeColor = theme.accentGreen || "rgba(34, 197, 94, 0.88)";

  const dataFixed = [];
  const dataCoveredNegative = [];
  const dataVariable = [];
  const variableBackground = [];
  const exportMode = chartMode === "export";
  const fixedPriceModeOnly = chartData.every((item) => (item.purchase_fixed == null ? fixedPriceMode : !!item.purchase_fixed));

  chartData.forEach((item) => {
    let fixed = null;
    let coveredNegative = null;
    let variable = null;

    const pointFixedPriceMode = item.purchase_fixed == null ? fixedPriceMode : !!item.purchase_fixed;
    if (exportMode) {
      // Export bars are one series: sale price (spot or fixed) minus the sale
      // coefficient. Import fees and distribution charges never apply here.
      variable = item.final == null ? null : Number(Number(item.final).toFixed(4));
    } else if (pointFixedPriceMode) {
      const hasCommodity = Number.isFinite(Number(item.purchase_fixed_price));
      if (hasCommodity) {
        const commodity = Number(item.purchase_fixed_price);
        const fees = Number(item.final) - commodity;
        // Distribution fees form the bottom of the bar, the commercial part
        // sits on top of them.
        fixed = fees !== 0 ? Number(fees.toFixed(4)) : null;
        variable = commodity > 0 ? Number(commodity.toFixed(4)) : null;
      } else {
        // No commodity split available: the whole price belongs to the
        // bottom (fees) series, never to the top one.
        fixed = Number(Number(item.final).toFixed(4));
        variable = null;
      }
    } else if (item.spot < 0) {
      const finalPrice = item.extra + item.spot;
      if (finalPrice >= 0) {
        fixed = finalPrice > 0 ? Number(finalPrice.toFixed(4)) : null;
        coveredNegative = Math.abs(item.spot) > 0 ? Number(Math.abs(item.spot).toFixed(4)) : null;
      } else {
        coveredNegative = item.extra > 0 ? Number(item.extra.toFixed(4)) : null;
        variable = finalPrice < 0 ? Number(finalPrice.toFixed(4)) : null;
      }
    } else {
      fixed = item.extra > 0 ? Number(item.extra.toFixed(4)) : null;
      variable = item.spot > 0 ? Number(item.spot.toFixed(4)) : null;

      if (item.extra === 0 && item.spot === 0) {
        fixed = 0;
      }
    }

    dataFixed.push(fixed);
    dataCoveredNegative.push(coveredNegative);
    dataVariable.push(variable);
    variableBackground.push(item.final < 0 ? negativeColor : colorScale(item.final, minFinal, maxFinal));
  });

  const datasets = exportMode
    ? [
        {
          type: "bar",
          label: "Prodejní cena",
          data: dataVariable,
          backgroundColor: variableBackground.map((color, index) => (dataVariable[index] != null ? (dataVariable[index] < 0 ? variableColor : negativeColor) : color)),
          borderRadius: 5,
          borderSkipped: false,
          stack: "price",
          barPercentage: 0.9,
          categoryPercentage: 1,
        },
      ]
    : [
        {
          type: "bar",
          label: fixedPriceModeOnly ? "Distribuční poplatky" : "Fixní složka",
          data: dataFixed,
          backgroundColor: fixedColor,
          borderRadius: 5,
          borderSkipped: false,
          stack: "price",
          barPercentage: 0.9,
          categoryPercentage: 1,
        },
        {
          type: "bar",
          label: "Pokryto zápornou cenou",
          data: dataCoveredNegative,
          backgroundColor: coveredNegativeColor,
          borderColor: coveredNegativeColor,
          borderWidth: 1,
          borderRadius: 5,
          borderSkipped: false,
          stack: "price",
          barPercentage: 0.9,
          categoryPercentage: 1,
        },
        {
          type: "bar",
          label: fixedPriceModeOnly ? "Obchodní část" : "Variabilní složka",
          data: dataVariable,
          backgroundColor: variableBackground.map((color, index) => (dataVariable[index] != null ? (dataVariable[index] < 0 ? negativeColor : variableColor) : color)),
          borderRadius: 5,
          borderSkipped: false,
          stack: "price",
          barPercentage: 0.9,
          categoryPercentage: 1,
        },
      ];

  return {
    title,
    pointPayloads: chartData,
    data: {
      labels: buildStaticTimeLabels(chartData),
      datasets,
    },
    options: {
      interaction: {
        mode: "index",
        intersect: false,
      },
      scales: {
        x: {
          ...buildCategoryTimeAxis({
            tickColor: (ctx) => (getVTStatus(ctx.tick.value, vtPeriods) === "VT" ? theme.accentRed : theme.accentGreen),
            minLabelWidth: 68,
          }),
          stacked: true,
        },
        y: {
          ...buildLinearAxis({ title: "Kč/kWh" }),
          stacked: true,
          grid: {
            color: "rgba(148, 163, 184, 0.12)",
          },
          ticks: {
            callback: (value) => `${Number(value).toFixed(2).replace(".", ",")}`,
          },
        },
      },
      plugins: {
        legend: {
          labels: {
            padding: 18,
            filter: () => true,
          },
        },
        tooltip: buildTooltip(({ points }) => {
          const point = chartData[points?.[0]?.dataIndex] || null;
          if (!point) return null;

          if (exportMode) {
            const exportPrice = Number(point.final);
            return {
              title: `${formatSlotToTime(point.slot)} (${getVTStatus(point.slot, vtPeriods)})`,
              sections: [
                {
                  label: "Prodejní cena",
                  value: `${Number.isFinite(exportPrice) ? exportPrice.toFixed(2) : "-"} Kč`,
                  color: exportPrice < 0 ? variableColor : negativeColor,
                },
              ],
            };
          }

          const sections = [];
          const pointFixedPriceMode = point.purchase_fixed == null ? fixedPriceMode : !!point.purchase_fixed;
          if (pointFixedPriceMode) {
            sections.push({ label: "Fixní složka", value: `${point.purchase_fixed_price?.toFixed(2) ?? point.final?.toFixed(2) ?? "-"} Kč`, color: fixedColor });
            const variablePart = Number(point.final) - Number(point.purchase_fixed_price ?? point.final);
            if (variablePart) sections.push({ label: "Variabilní složka", value: `${variablePart.toFixed(2)} Kč`, color: variableColor });
          } else {
            sections.push({ label: "Fixní složka", value: `${point.extra?.toFixed(2) ?? "-"} Kč`, color: fixedColor });
          }

          if (!pointFixedPriceMode && point.spot < 0) {
            sections.push({ label: "Záporná var. složka", value: `${point.spot?.toFixed(2) ?? "-"} Kč`, color: coveredNegativeColor });
          } else if (!pointFixedPriceMode) {
            sections.push({ label: "Variabilní složka", value: `${point.spot?.toFixed(2) ?? "-"} Kč`, color: variableColor });
          }

          sections.push({ label: "Konečná cena", value: `${point.final?.toFixed(2) ?? "-"} Kč`, color: theme.text });

          return {
            title: `${formatSlotToTime(point.slot)} (${getVTStatus(point.slot, vtPeriods)})`,
            sections,
          };
        }),
        annotation: {
          annotations: {
            ...buildTimeBandAnnotations(buildVtBands(vtPeriods)),
            ...buildCurrentSlotAnnotations({ slot: activeSlot }),
            ...(thresholds ? buildThresholdAnnotations({
              minThreshold: thresholds.min_price_today,
              maxThreshold: thresholds.max_price_today,
            }) : {}),
          },
        },
      },
    },
  };
};
