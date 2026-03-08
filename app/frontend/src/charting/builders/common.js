import { formatSlotToTime } from "../../utils/formatters";
import { createExternalTooltip } from "../plugins/externalTooltipPlugin";

export const quarterHourTickFormatter = (value) => {
  if (!Number.isFinite(value)) {
    return "";
  }
  return formatSlotToTime(value);
};

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

