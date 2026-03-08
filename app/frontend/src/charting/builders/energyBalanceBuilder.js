import { buildTooltip } from "./common";

export const ENERGY_SERIES = [
  { key: "grid_export_kwh", name: "Export grid", color: "#4d79ff" },
  { key: "grid_import_kwh", name: "Import grid", color: "#ff4d4f" },
  { key: "pv_kwh", name: "PV vyroba", color: "#f2c230" },
  { key: "house_load_kwh", name: "Spotreba domu", color: "#c7392f" },
];

const formatKwh = (value) => (value == null || Number.isNaN(value) ? "-" : `${Number(value).toFixed(2)} kWh`);

const buildTooltipModel = (points, rows) => {
  const point = rows[points?.[0]?.dataIndex] || null;
  if (!point) {
    return null;
  }

  return {
    title: point.label || "-",
    sections: ENERGY_SERIES.map((series) => ({
      label: series.name,
      value: formatKwh(point[series.key]),
      color: series.color,
    })),
  };
};

export const buildEnergyBalanceLineConfig = (points) => ({
  pointPayloads: points,
  data: {
    labels: points.map((point) => point.label),
    datasets: ENERGY_SERIES.map((series) => ({
      type: "line",
      label: series.name,
      data: points.map((point) => point[series.key] ?? 0),
      borderColor: series.color,
      backgroundColor: `${series.color}22`,
      borderWidth: 2.5,
      pointRadius: 0,
      pointHoverRadius: 4,
      tension: 0.28,
    })),
  },
  options: {
    interaction: {
      mode: "index",
      intersect: false,
    },
    scales: {
      x: {
        type: "category",
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "kWh",
        },
      },
    },
    plugins: {
      tooltip: buildTooltip(({ points: tooltipPoints }) => buildTooltipModel(tooltipPoints, points)),
    },
  },
});

export const buildEnergyBalanceBarConfig = (points) => ({
  pointPayloads: points,
  data: {
    labels: points.map((point) => point.label),
    datasets: ENERGY_SERIES.map((series) => ({
      type: "bar",
      label: series.name,
      data: points.map((point) => point[series.key] ?? 0),
      backgroundColor: series.color,
      borderRadius: 6,
      borderSkipped: false,
      barPercentage: 0.9,
      categoryPercentage: 0.82,
    })),
  },
  options: {
    interaction: {
      mode: "index",
      intersect: false,
    },
    scales: {
      x: {
        type: "category",
        stacked: false,
      },
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "kWh",
        },
      },
    },
    plugins: {
      tooltip: buildTooltip(({ points: tooltipPoints }) => buildTooltipModel(tooltipPoints, points)),
    },
  },
});

