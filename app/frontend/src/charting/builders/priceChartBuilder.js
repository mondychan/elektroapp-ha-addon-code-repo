import { formatSlotToTime } from "../../utils/formatters";
import { buildCurrentSlotAnnotations } from "../plugins/currentSlotPlugin";
import { buildTimeBandAnnotations } from "../plugins/timeBandPlugin";
import { buildCategoryTimeAxis, buildLinearAxis, buildStaticTimeLabels, buildTooltip, colorScale } from "./common";

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

  const datasets = [
    {
      type: "bar",
      label: "Fixni slozka",
      data: chartData.map((item) => item.extra),
      backgroundColor: "rgba(45, 127, 249, 0.88)",
      borderRadius: 7,
      borderSkipped: false,
      stack: "price",
      barPercentage: 0.92,
      categoryPercentage: 1,
    },
    {
      type: "bar",
      label: "Variabilni slozka",
      data: chartData.map((item) => item.spot),
      backgroundColor: chartData.map((item) => colorScale(item.final, minFinal, maxFinal)),
      borderRadius: 7,
      borderSkipped: false,
      stack: "price",
      barPercentage: 0.92,
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
      scales: {
        x: {
          ...buildCategoryTimeAxis({
            tickColor: (ctx) => (getVTStatus(ctx.tick.value, vtPeriods) === "VT" ? "#c7392f" : "#2f8f49"),
          }),
          stacked: true,
        },
        y: {
          ...buildLinearAxis({ title: "Cena" }),
          stacked: true,
          ticks: {
            callback: (value) => `${Number(value).toFixed(2)},-Kc`,
          },
        },
      },
    plugins: {
        legend: {
          labels: {},
        },
        tooltip: buildTooltip(({ points }) => {
          const point = chartData[points?.[0]?.dataIndex] || null;
          if (!point) {
            return null;
          }
          return {
            title: `${formatSlotToTime(point.slot)} (${getVTStatus(point.slot, vtPeriods)})`,
            sections: [
              { label: "Fixni slozka", value: `${point.extra.toFixed(2)},-Kc`, color: "rgba(45, 127, 249, 0.88)" },
              { label: "Variabilni slozka", value: `${point.spot.toFixed(2)},-Kc`, color: "rgba(255, 122, 89, 0.84)" },
              { label: "Konecna cena", value: `${point.final.toFixed(2)},-Kc`, color: "rgba(255, 255, 255, 0.92)" },
            ],
          };
        }),
        annotation: {
          annotations: {
            ...buildTimeBandAnnotations(buildVtBands(vtPeriods)),
            ...buildCurrentSlotAnnotations({ slot: activeSlot }),
          },
        },
      },
    },
  };
};
