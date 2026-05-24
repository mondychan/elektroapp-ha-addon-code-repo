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

  chartData.forEach((item) => {
    let fixed = null;
    let coveredNegative = null;
    let variable = null;

    if (item.spot < 0) {
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

  const datasets = [
    {
      type: "bar",
      label: "Fixní složka",
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
      label: "Variabilní složka",
      data: dataVariable,
      backgroundColor: variableBackground.map((color, index) => (dataVariable[index] != null ? variableColor : color)),
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

          const sections = [
            { label: "Fixní složka", value: `${point.extra?.toFixed(2) ?? "-"} Kč`, color: fixedColor },
          ];

          if (point.spot < 0) {
            sections.push({ label: "Záporná var. složka", value: `${point.spot?.toFixed(2) ?? "-"} Kč`, color: coveredNegativeColor });
          } else {
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
