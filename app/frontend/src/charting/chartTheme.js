import { ensureChartJsRegistered } from "./chartjs/register";

const DEFAULT_THEME = {
  panel: "#ffffff",
  panel2: "#f7fbff",
  text: "#1b1e22",
  textMuted: "#5f6b7a",
  border: "#d7dee7",
  rowBorder: "#edf1f5",
  accent: "#ff7a59",
  accent2: "#2d7ff9",
  shadow: "rgba(16, 24, 40, 0.12)",
  buy: "#e7a52a",
  sell: "#39b56a",
  danger: "#d46a6a",
  grid: "rgba(95, 107, 122, 0.18)",
  tooltipShadow: "rgba(15, 23, 42, 0.18)",
};

const readCssVar = (styles, name, fallback) => {
  const value = styles?.getPropertyValue(name)?.trim();
  return value || fallback;
};

export const getChartTheme = () => {
  if (typeof window === "undefined" || !window.getComputedStyle) {
    return DEFAULT_THEME;
  }

  const styles = window.getComputedStyle(document.body);
  return {
    panel: readCssVar(styles, "--panel", DEFAULT_THEME.panel),
    panel2: readCssVar(styles, "--panel-2", DEFAULT_THEME.panel2),
    text: readCssVar(styles, "--text", DEFAULT_THEME.text),
    textMuted: readCssVar(styles, "--text-muted", DEFAULT_THEME.textMuted),
    border: readCssVar(styles, "--border", DEFAULT_THEME.border),
    rowBorder: readCssVar(styles, "--row-border", DEFAULT_THEME.rowBorder),
    accent: readCssVar(styles, "--accent", DEFAULT_THEME.accent),
    accent2: readCssVar(styles, "--accent-2", DEFAULT_THEME.accent2),
    shadow: DEFAULT_THEME.shadow,
    buy: DEFAULT_THEME.buy,
    sell: DEFAULT_THEME.sell,
    danger: DEFAULT_THEME.danger,
    grid: DEFAULT_THEME.grid,
    tooltipShadow: DEFAULT_THEME.tooltipShadow,
  };
};

export const getHeatmapColor = (metric, ratio, hasValue = true, theme = getChartTheme()) => {
  if (!hasValue) {
    return theme.panel2;
  }

  const clamped = Math.max(0, Math.min(1, ratio));
  if (metric === "price") {
    const hue = 120 - (120 * clamped);
    return `hsla(${hue}, 75%, 52%, 0.72)`;
  }
  if (metric === "export") {
    return `hsla(145, 70%, ${35 + clamped * 25}%, ${0.2 + clamped * 0.58})`;
  }
  return `hsla(28, 88%, ${38 + clamped * 20}%, ${0.18 + clamped * 0.66})`;
};

export const applyChartDefaults = (theme) => {
  const ChartJS = ensureChartJsRegistered();
  const fontFamily =
    typeof window !== "undefined" && window.getComputedStyle
      ? window.getComputedStyle(document.body).fontFamily
      : "\"Candara\", \"Segoe UI\", \"Tahoma\", sans-serif";

  ChartJS.defaults.color = theme.text;
  ChartJS.defaults.font.family = fontFamily;
  ChartJS.defaults.borderColor = theme.border;
  ChartJS.defaults.scale.grid.color = theme.grid;
  ChartJS.defaults.scale.grid.borderDash = [3, 4];
  ChartJS.defaults.scale.ticks.color = theme.textMuted;
  ChartJS.defaults.plugins.legend.labels.color = theme.text;
  ChartJS.defaults.plugins.legend.labels.boxWidth = 12;
  ChartJS.defaults.plugins.legend.labels.boxHeight = 12;
  ChartJS.defaults.plugins.legend.labels.usePointStyle = true;
  ChartJS.defaults.plugins.legend.position = "top";
  ChartJS.defaults.plugins.tooltip.enabled = false;
  ChartJS.defaults.maintainAspectRatio = false;
  ChartJS.defaults.responsive = true;
  ChartJS.defaults.animation = false;
};
