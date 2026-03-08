/**
 * @typedef {"none" | "soft" | "progressive" | "realtime"} ChartAnimationProfile
 */

const makeProgressiveDelay = (step = 20) => (ctx) => {
  if (ctx.type !== "data" || ctx.mode === "none") {
    return 0;
  }
  return (ctx.datasetIndex * 90) + (ctx.dataIndex * step);
};

export const animationProfiles = {
  none: false,
  soft: {
    duration: 520,
    easing: "easeOutCubic",
  },
  progressive: {
    x: {
      type: "number",
      easing: "linear",
      duration: 0,
      from: NaN,
    },
    y: {
      type: "number",
      easing: "easeOutQuart",
      duration: 820,
      from: (ctx) => {
        const yScale = ctx.chart.scales?.y || ctx.chart.scales?.yCost || ctx.chart.scales?.ySoc;
        return yScale ? yScale.getPixelForValue(0) : undefined;
      },
      delay: makeProgressiveDelay(18),
    },
  },
  realtime: {
    duration: 260,
    easing: "easeOutQuad",
  },
};

export const resolveAnimationProfile = (profile = "soft") => animationProfiles[profile] || animationProfiles.soft;

