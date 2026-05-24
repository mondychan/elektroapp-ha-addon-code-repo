import { getChartTheme } from "../chartTheme";
import { buildLinearAxis, getResponsiveTickStep } from "./common";

const formatHourLabel = (value) => {
  if (!Number.isFinite(value)) return "";
  return `${String(Math.round(value)).padStart(2, "0")}:00`;
};

const THEME_COLORS = {
  solar: { bg: "rgba(245, 158, 11, 0.6)", border: "#f59e0b" },
  predicted: { bg: "rgba(245, 158, 11, 0.22)", border: "rgba(245, 158, 11, 0.45)", dash: [8, 4] },
  load: { bg: "rgba(34, 211, 238, 0.3)", border: "#22d3ee" },
  import: { bg: "rgba(239, 68, 68, 0.5)", border: "#ef4444" },
  export: { bg: "rgba(56, 189, 248, 0.5)", border: "#38bdf8" },
  cloudCover: { bg: "rgba(148, 163, 184, 0.10)", border: "rgba(148, 163, 184, 0.3)" },
};

export const buildSolarOverviewForecastConfig = ({ points, now, theme }) => {
  const chartTheme = theme || getChartTheme();
  const hourCount = points.length || 24;

  const generatedData = points.map((p) => p.generated_w);
  const predictedData = points.map((p) => p.predicted_w);
  const cloudData = points.map((p) => p.cloud_cover_percent);

  return {
    pointPayloads: points,
    data: {
      labels: points.map((_, i) => i),
      datasets: [
        {
          type: "bar",
          label: "Vyrobeno",
          yAxisID: "yPower",
          data: generatedData,
          backgroundColor: THEME_COLORS.solar.bg,
          borderColor: THEME_COLORS.solar.border,
          borderWidth: 1,
          order: 2,
        },
        {
          type: "line",
          label: "Predikce",
          yAxisID: "yPower",
          data: predictedData,
          borderColor: THEME_COLORS.predicted.border,
          backgroundColor: "transparent",
          borderWidth: 2,
          borderDash: THEME_COLORS.predicted.dash,
          pointRadius: 0,
          tension: 0.3,
          order: 1,
          spanGaps: false,
        },
        {
          type: "line",
          label: "Oblačnost",
          yAxisID: "yCloud",
          data: cloudData,
          borderColor: THEME_COLORS.cloudCover.border,
          backgroundColor: THEME_COLORS.cloudCover.bg,
          borderWidth: 1.5,
          pointRadius: 0,
          fill: true,
          tension: 0.3,
          order: 0,
          spanGaps: false,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "linear",
          min: -0.5,
          max: hourCount - 0.5,
          offset: false,
          grid: { display: false },
          ticks: {
            stepSize: 1,
            callback(value) {
              const step = getResponsiveTickStep({
                chart: this.chart,
                labelCount: hourCount,
                baseStep: 1,
                minLabelWidth: 38,
              });
              if (!Number.isFinite(value) || value % step !== 0) return "";
              return formatHourLabel(value);
            },
            maxRotation: 0,
            minRotation: 0,
            color: chartTheme.textMuted,
          },
        },
        yPower: buildLinearAxis({ title: "W", position: "left", color: chartTheme.textMuted }),
        yCloud: buildLinearAxis({ title: "%", position: "right", color: chartTheme.textMuted, suggestedMax: 100 }),
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: chartTheme.textMuted, usePointStyle: true, boxWidth: 12 },
        },
        tooltip: {
          callbacks: {
            title(items) {
              const idx = items[0]?.dataIndex;
              return points[idx]?.time?.slice(11, 16) || formatHourLabel(idx);
            },
            label(ctx) {
              const point = points[ctx.dataIndex];
              if (!point) return "";
              switch (ctx.dataset.label) {
                case "Vyrobeno": return `Vyrobeno: ${point.generated_w != null ? `${point.generated_w} W` : "-"}`;
                case "Predikce": return `Predikce: ${point.predicted_w != null ? `${point.predicted_w} W` : "-"}`;
                case "Oblačnost":
                  return [
                    `Oblačnost: ${point.cloud_cover_percent != null ? `${point.cloud_cover_percent} %` : "-"}`,
                    point.temperature_c != null ? `Teplota: ${point.temperature_c} °C` : null,
                    point.condition ? `Počasí: ${point.condition}` : null,
                  ].filter(Boolean);
                default: return "";
              }
            },
          },
        },
      },
    },
  };
};

export const buildSolarOverviewEnergyConfig = ({ points, theme }) => {
  const chartTheme = theme || getChartTheme();

  return {
    pointPayloads: points,
    data: {
      labels: points.map((p) => p.time?.slice(11, 16) || ""),
      datasets: [
        {
          type: "line",
          label: "Soláry",
          data: points.map((p) => p.solar_pv_w),
          borderColor: THEME_COLORS.solar.border,
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          spanGaps: false,
        },
        {
          type: "line",
          label: "Dům",
          data: points.map((p) => p.load_w),
          borderColor: THEME_COLORS.load.border,
          backgroundColor: "transparent",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          spanGaps: false,
        },
        {
          type: "bar",
          label: "Import",
          data: points.map((p) => p.grid_import_w),
          backgroundColor: THEME_COLORS.import.bg,
          borderColor: THEME_COLORS.import.border,
          borderWidth: 1,
        },
        {
          type: "bar",
          label: "Export",
          data: points.map((p) => p.grid_export_w),
          backgroundColor: THEME_COLORS.export.bg,
          borderColor: THEME_COLORS.export.border,
          borderWidth: 1,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      scales: {
        x: {
          type: "category",
          ticks: {
            autoSkip: true,
            maxRotation: 0,
            minRotation: 0,
            callback(value, index) {
              const step = getResponsiveTickStep({
                chart: this.chart,
                labelCount: points.length,
                baseStep: 4,
                minLabelWidth: 42,
              });
              return index % step === 0 ? this.getLabelForValue(value) : "";
            },
            color: chartTheme.textMuted,
          },
          grid: { display: false },
        },
        y: buildLinearAxis({ title: "W", color: chartTheme.textMuted }),
      },
      plugins: {
        legend: {
          position: "bottom",
          labels: { color: chartTheme.textMuted, usePointStyle: true, boxWidth: 12 },
        },
        tooltip: {
          callbacks: {
            title(items) {
              return items[0]?.label || "";
            },
            label(ctx) {
              const point = points[ctx.dataIndex];
              if (!point) return "";
              const val = ctx.raw;
              const formatted = val != null ? `${val} W` : "-";
              return `${ctx.dataset.label}: ${formatted}`;
            },
          },
        },
      },
    },
  };
};

export const weatherConditionIcon = (condition) => {
  const map = {
    sunny: "\u2600\uFE0F",
    "clear-night": "\uD83C\uDF19",
    partlycloudy: "\u26C5",
    cloudy: "\u2601\uFE0F",
    rainy: "\uD83C\uDF27\uFE0F",
    snowy: "\uD83C\uDF28\uFE0F",
    fog: "\uD83C\uDF2B\uFE0F",
    windy: "\uD83D\uDCA8",
    lightning: "\u26A1",
    "lightning-rainy": "\u26C8\uFE0F",
    pouring: "\uD83C\uDF27\uFE0F",
    hail: "\uD83C\uDF28\uFE0F",
  };
  return map[condition] || map.unknown || "\u2753";
};
