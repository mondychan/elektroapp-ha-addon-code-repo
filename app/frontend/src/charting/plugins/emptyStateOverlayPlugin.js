export const emptyStateOverlayPlugin = {
  id: "emptyStateOverlay",
  afterDraw(chart, _args, pluginOptions) {
    if (!pluginOptions?.display || !pluginOptions?.message) {
      return;
    }

    const datasets = chart.data?.datasets || [];
    const hasVisibleValue = datasets.some((dataset) =>
      (dataset?.data || []).some((point) => {
        if (point == null) {
          return false;
        }
        if (typeof point === "number") {
          return Number.isFinite(point);
        }
        if (typeof point?.y === "number") {
          return Number.isFinite(point.y);
        }
        if (typeof point?.v === "number") {
          return Number.isFinite(point.v);
        }
        return false;
      })
    );

    if (hasVisibleValue) {
      return;
    }

    const { ctx, chartArea } = chart;
    if (!chartArea) {
      return;
    }

    ctx.save();
    ctx.fillStyle = pluginOptions.color || "rgba(95, 107, 122, 0.9)";
    ctx.font = pluginOptions.font || "500 13px Candara, Segoe UI, Tahoma, sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(
      pluginOptions.message,
      (chartArea.left + chartArea.right) / 2,
      (chartArea.top + chartArea.bottom) / 2
    );
    ctx.restore();
  },
};

