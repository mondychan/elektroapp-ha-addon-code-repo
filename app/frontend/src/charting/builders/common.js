import { formatSlotToTime } from "../../utils/formatters";
import { createExternalTooltip } from "../plugins/externalTooltipPlugin";

export const STATIC_SLOT_TICK_STEP = 8;

export const getResponsiveTickStep = ({ chart, labelCount = 0, baseStep = 1, minLabelWidth = 56 }) => {
  const safeLabelCount = Math.max(labelCount, 1);
  const chartWidth = chart?.chartArea?.width || chart?.width || 0;
  const maxVisibleLabels = Math.max(2, Math.floor(chartWidth / minLabelWidth));
  const rawStep = Math.max(baseStep, Math.ceil(safeLabelCount / maxVisibleLabels));
  return Math.max(baseStep, Math.ceil(rawStep / baseStep) * baseStep);
};

export const quarterHourTickFormatter = (value) => {
  if (!Number.isFinite(value)) {
    return "";
  }
  return formatSlotToTime(value);
};

export const staticSlotTickFormatter = (value) => {
  if (!Number.isFinite(value) || value % STATIC_SLOT_TICK_STEP !== 0) {
    return "";
  }
  return formatSlotToTime(value);
};

export const buildStaticTimeLabels = (rows = []) => rows.map((row) => row.time || formatSlotToTime(row.slot));

export const buildCategoryTimeAxis = ({
  stepSize = STATIC_SLOT_TICK_STEP,
  labelFormatter = (index) => staticSlotTickFormatter(index),
  tickColor,
  minLabelWidth = 56,
} = {}) => ({
  type: "category",
  offset: false,
  grid: {
    display: false,
  },
  ticks: {
    autoSkip: false,
    maxRotation: 0,
    minRotation: 0,
    callback(value) {
      const responsiveStep = getResponsiveTickStep({
        chart: this.chart,
        labelCount: this.chart?.data?.labels?.length || 0,
        baseStep: stepSize,
        minLabelWidth,
      });
      if (!Number.isFinite(value) || value % responsiveStep !== 0) {
        return "";
      }
      return labelFormatter(value, this.getLabelForValue(value));
    },
    color: tickColor,
  },
});

export const buildSlotAxis = ({
  max = 95,
  stepSize = 8,
  includeBandPadding = false,
  labelFormatter = quarterHourTickFormatter,
} = {}) => ({
  type: "linear",
  min: includeBandPadding ? -0.5 : 0,
  max: includeBandPadding ? max + 0.5 : max,
  offset: false,
  grid: {
    display: false,
  },
  ticks: {
    stepSize,
    callback: (value) => labelFormatter(value),
  },
});

export const buildLinearAxis = ({ title, position = "left", suggestedMax, grace, color } = {}) => ({
  type: "linear",
  position,
  grace,
  suggestedMax,
  title: title
    ? {
        display: true,
        text: title,
        color,
      }
    : undefined,
});

export const buildTooltip = (renderTooltip) =>
  createExternalTooltip({
    renderTooltip,
  });

export const colorScale = (value, min, max) => {
  if (!Number.isFinite(value) || !Number.isFinite(min) || !Number.isFinite(max) || max <= min) {
    return "rgba(255, 122, 89, 0.74)";
  }
  const ratio = Math.max(0, Math.min(1, (value - min) / (max - min)));
  const start = { r: 45, g: 127, b: 249 };
  const end = { r: 255, g: 122, b: 89 };
  const r = Math.round(start.r + (end.r - start.r) * ratio);
  const g = Math.round(start.g + (end.g - start.g) * ratio);
  const b = Math.round(start.b + (end.b - start.b) * ratio);
  return `rgba(${r}, ${g}, ${b}, 0.84)`;
};
