import { getChartTheme, getHeatmapColor } from "../chartTheme";
import { buildTooltip, getResponsiveTickStep } from "./common";

const formatCellValue = (value, metric) => {
  if (value == null) return "-";
  if (metric === "price") return `${Number(value).toFixed(2)} Kc/kWh`;
  return `${Number(value).toFixed(3)} kWh`;
};

export const buildHeatmapChartConfig = ({ heatmapData, metric }) => {
  const theme = getChartTheme();
  const days = heatmapData?.days || [];
  const hours = heatmapData?.hours || Array.from({ length: 24 }, (_, i) => i);
  const min = heatmapData?.stats?.min;
  const max = heatmapData?.stats?.max;
  const denominator = max != null && min != null && max > min ? max - min : null;

  const pointPayloads = [];
  const matrixData = [];

  days.forEach((dayRow, dayIndex) => {
    dayRow.values.forEach((value, hourIndex) => {
      const ratio = value == null || denominator == null ? 0 : (value - min) / denominator;
      const payload = {
        date: dayRow.date,
        day: dayRow.day,
        hour: hourIndex,
        label: `${dayRow.date} ${String(hourIndex).padStart(2, "0")}:00`,
        value,
      };
      pointPayloads.push(payload);
      matrixData.push({
        x: hourIndex,
        y: dayIndex,
        v: value,
        payload,
        backgroundColor: getHeatmapColor(metric, denominator == null ? 1 : ratio, value != null, theme),
      });
    });
  });

  return {
    pointPayloads,
    data: {
      datasets: [
        {
          label: "Heatmap",
          data: matrixData,
          backgroundColor: (ctx) => ctx.raw?.backgroundColor || "rgba(255,255,255,0.08)",
          borderColor: theme.border,
          borderWidth: 1,
          width: ({ chart }) => {
            const xScale = chart.scales.x;
            return xScale ? Math.max(16, xScale.width / Math.max(hours.length, 1) - 2) : 18;
          },
          height: ({ chart }) => {
            const yScale = chart.scales.y;
            return yScale ? Math.max(14, yScale.height / Math.max(days.length, 1) - 2) : 16;
          },
        },
      ],
    },
    options: {
      parsing: false,
      scales: {
        x: {
          type: "linear",
          min: -0.5,
          max: hours.length - 0.5,
          offset: false,
          grid: {
            display: false,
          },
          ticks: {
            stepSize: 1,
            callback(value) {
              const responsiveStep = getResponsiveTickStep({
                chart: this.chart,
                labelCount: hours.length,
                baseStep: 1,
                minLabelWidth: 34,
              });
              if (!Number.isFinite(value) || value % responsiveStep !== 0) {
                return "";
              }
              return String(value).padStart(2, "0");
            },
            maxRotation: 0,
            minRotation: 0,
          },
        },
        y: {
          type: "linear",
          reverse: true,
          min: -0.5,
          max: days.length - 0.5,
          grid: {
            display: false,
          },
          ticks: {
            stepSize: 1,
            callback: (value) => days[value]?.day || "",
          },
        },
      },
      plugins: {
        legend: {
          display: false,
        },
        tooltip: buildTooltip(({ points }) => {
          const raw = points?.[0]?.raw?.payload;
          if (!raw) return null;
          return {
            title: raw.label,
            sections: [{ label: "Hodnota", value: formatCellValue(raw.value, metric), color: raw.value == null ? "#9aa7b5" : "#ffffff" }],
          };
        }),
      },
    },
  };
};
