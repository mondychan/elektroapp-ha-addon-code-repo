import { buildQuarterHourSeries } from "../../utils/timeSeries";
import { buildTransitionAnnotations } from "../plugins/transitionAnnotationPlugin";
import { buildCategoryTimeAxis, buildLinearAxis, buildStaticTimeLabels, buildTooltip } from "./common";

export const buildCostChartData = (costs) => {
  if (!costs?.length) return [];
  const rows = buildQuarterHourSeries(
    costs,
    (point) => ({
      kwh: Number.isFinite(point?.kwh) ? point.kwh : 0,
      cost: Number.isFinite(point?.cost) ? point.cost : 0,
    }),
    { kwh: 0, cost: 0 }
  );
  let costCumulative = 0;
  return rows.map((row) => {
    costCumulative += row.cost;
    return {
      ...row,
      costCumulative,
    };
  });
};

export const buildExportChartData = (exportPoints) => {
  if (!exportPoints?.length) return [];
  const rows = buildQuarterHourSeries(
    exportPoints,
    (point) => ({
      kwh: Number.isFinite(point?.kwh) ? point.kwh : 0,
      sell: Number.isFinite(point?.sell) ? point.sell : 0,
    }),
    { kwh: 0, sell: 0, sellCumulative: 0 }
  );
  let sellCumulative = 0;
  return rows.map((row) => {
    sellCumulative += row.sell;
    return {
      ...row,
      sellCumulative,
    };
  });
};

const buildComboConfig = ({
  chartData,
  barKey,
  lineKey,
  barLabel,
  lineLabel,
  transitions,
  lineColor,
  barColor,
}) => ({
  pointPayloads: chartData,
  data: {
    labels: buildStaticTimeLabels(chartData),
    datasets: [
      {
        type: "bar",
        label: barLabel,
        data: chartData.map((item) => item[barKey]),
        yAxisID: "yVolume",
        backgroundColor: barColor,
        borderRadius: 8,
        borderSkipped: false,
        barPercentage: 0.84,
        categoryPercentage: 0.94,
      },
      {
        type: "line",
        label: lineLabel,
        data: chartData.map((item) => item[lineKey]),
        yAxisID: "yValue",
        borderColor: lineColor,
        backgroundColor: lineColor,
        borderWidth: 3,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.32,
      },
    ],
  },
  options: {
    interaction: {
      mode: "index",
      intersect: false,
    },
    scales: {
      x: buildCategoryTimeAxis(),
      yVolume: {
        ...buildLinearAxis({ title: "kWh", position: "left", grace: "8%" }),
        beginAtZero: true,
        ticks: {
          callback: (value) => Number(value).toFixed(2),
        },
      },
      yValue: {
        ...buildLinearAxis({ title: "Kc", position: "right", grace: "10%" }),
        beginAtZero: true,
        grid: {
          drawOnChartArea: false,
        },
        ticks: {
          callback: (value) => `${Number(value).toFixed(2)},-Kc`,
        },
      },
    },
    plugins: {
      tooltip: buildTooltip(({ points }) => {
        const point = chartData[points?.[0]?.dataIndex] || null;
        if (!point) {
          return null;
        }
        return {
          title: point.time,
          sections: [
            { label: barLabel, value: `${point[barKey].toFixed(3)} kWh`, color: barColor },
            { label: lineLabel, value: `${point[lineKey].toFixed(2)},-Kc`, color: lineColor },
          ],
        };
      }),
      annotation: {
        annotations: buildTransitionAnnotations(transitions),
      },
    },
  },
});

export const buildCostChartConfig = (chartData, showAnnotations = false) =>
  buildComboConfig({
    chartData,
    barKey: "kwh",
    lineKey: "costCumulative",
    barLabel: "Nakup kWh",
    lineLabel: "Kumulativni naklad",
    transitions: [],
    lineColor: "rgba(45, 127, 249, 0.94)",
    barColor: "rgba(231, 165, 42, 0.82)",
  });

export const buildExportChartConfig = (chartData, showAnnotations = false) =>
  buildComboConfig({
    chartData,
    barKey: "kwh",
    lineKey: "sellCumulative",
    barLabel: "Export kWh",
    lineLabel: "Kumulativni trzby",
    transitions: [],
    lineColor: "rgba(57, 181, 106, 0.96)",
    barColor: "rgba(77, 121, 255, 0.78)",
  });
