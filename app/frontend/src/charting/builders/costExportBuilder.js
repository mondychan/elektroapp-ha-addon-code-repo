import { buildQuarterHourSeries } from "../../utils/timeSeries";
import { buildTransitionAnnotations } from "../plugins/transitionAnnotationPlugin";
import { buildLinearAxis, buildSlotAxis, buildTooltip } from "./common";

export const buildCostChartData = (costs) => {
  if (!costs?.length) return [];
  return buildQuarterHourSeries(
    costs,
    (point) => ({
      kwh: Number.isFinite(point?.kwh) ? point.kwh : 0,
      cost: Number.isFinite(point?.cost) ? point.cost : 0,
    }),
    { kwh: 0, cost: 0 }
  );
};

export const buildExportChartData = (exportPoints) => {
  if (!exportPoints?.length) return [];
  return buildQuarterHourSeries(
    exportPoints,
    (point) => ({
      kwh: Number.isFinite(point?.kwh) ? point.kwh : 0,
      sell: Number.isFinite(point?.sell) ? point.sell : 0,
    }),
    { kwh: 0, sell: 0 }
  );
};

const buildTransitions = (chartData, predicate, labels) => {
  const events = [];
  let wasActive = false;
  chartData.forEach((row) => {
    const isActive = predicate(row);
    if (isActive && !wasActive) {
      events.push({ slot: row.slot, kind: "start", label: labels.start });
    } else if (!isActive && wasActive) {
      events.push({ slot: row.slot, kind: "stop", label: labels.stop });
    }
    wasActive = isActive;
  });
  return events;
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
    datasets: [
      {
        type: "bar",
        label: barLabel,
        data: chartData.map((item) => ({ x: item.slot, y: item[barKey] })),
        parsing: false,
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
        data: chartData.map((item) => ({ x: item.slot, y: item[lineKey] })),
        parsing: false,
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
    parsing: false,
    interaction: {
      mode: "index",
      intersect: false,
    },
    scales: {
      x: buildSlotAxis({ includeBandPadding: true }),
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
    lineKey: "cost",
    barLabel: "Nakup kWh",
    lineLabel: "Naklad",
    transitions: showAnnotations
      ? buildTransitions(chartData, (row) => row.kwh > 0, { start: "Nakup start", stop: "Nakup stop" })
      : [],
    lineColor: "rgba(45, 127, 249, 0.94)",
    barColor: "rgba(231, 165, 42, 0.82)",
  });

export const buildExportChartConfig = (chartData, showAnnotations = false) =>
  buildComboConfig({
    chartData,
    barKey: "kwh",
    lineKey: "sell",
    barLabel: "Export kWh",
    lineLabel: "Trzby",
    transitions: showAnnotations
      ? buildTransitions(chartData, (row) => row.kwh > 0, { start: "Export start", stop: "Export stop" })
      : [],
    lineColor: "rgba(57, 181, 106, 0.96)",
    barColor: "rgba(77, 121, 255, 0.78)",
  });

