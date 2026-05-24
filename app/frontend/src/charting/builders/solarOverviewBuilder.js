import { getChartTheme } from "../chartTheme";
import { buildLinearAxis, buildTooltip, getResponsiveTickStep } from "./common";

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
        tooltip: buildTooltip(({ points: tipPoints }) => {
          if (!tipPoints?.length) return null;
          const idx = tipPoints[0]?.dataIndex;
          const point = points[idx];
          if (!point) return null;
          const sections = [];
          for (const tp of tipPoints) {
            switch (tp.dataset.label) {
              case "Vyrobeno":
                sections.push({ label: "Vyrobeno", value: tp.raw != null ? `${tp.raw} W` : "-", color: THEME_COLORS.solar.border });
                break;
              case "Predikce":
                sections.push({ label: "Predikce", value: tp.raw != null ? `${tp.raw} W` : "-", color: THEME_COLORS.predicted.border });
                break;
              case "Oblačnost":
                if (point.cloud_cover_percent != null)
                  sections.push({ label: "Oblačnost", value: `${point.cloud_cover_percent} %`, color: THEME_COLORS.cloudCover.border });
                if (point.temperature_c != null)
                  sections.push({ label: "Teplota", value: `${point.temperature_c} °C`, color: "#94a3b8" });
                if (point.condition)
                  sections.push({ label: "Počasí", value: point.condition, color: "#94a3b8" });
                break;
            }
          }
          return { title: point.time?.slice(11, 16) || formatHourLabel(idx), sections };
        }),
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
          yAxisID: "y",
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
          yAxisID: "y",
        },
        {
          type: "bar",
          label: "Import",
          data: points.map((p) => p.grid_import_w),
          backgroundColor: THEME_COLORS.import.bg,
          borderColor: THEME_COLORS.import.border,
          borderWidth: 1,
          yAxisID: "y",
          stack: "import-bar",
        },
        {
          type: "bar",
          label: "Export",
          data: points.map((p) => p.grid_export_w),
          backgroundColor: THEME_COLORS.export.bg,
          borderColor: THEME_COLORS.export.border,
          borderWidth: 1,
          yAxisID: "y",
          stack: "export-bar",
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
        tooltip: buildTooltip(({ points: tipPoints }) => {
          if (!tipPoints?.length) return null;
          const title = tipPoints[0]?.label || "";
          return {
            title,
            sections: tipPoints.map((tp) => ({
              label: tp.dataset.label,
              value: tp.raw != null ? `${tp.raw} W` : "-",
              color: tp.dataset.borderColor || tp.dataset.backgroundColor,
            })),
          };
        }),
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
  return map[condition] || "\u2753";
};
