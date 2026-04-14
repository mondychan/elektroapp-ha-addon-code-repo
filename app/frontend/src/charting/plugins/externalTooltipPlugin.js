const getOrCreateTooltipEl = (chart) => {
  const host = chart.canvas.parentNode;
  let tooltipEl = host.querySelector(".chartjs-html-tooltip");

  if (!tooltipEl) {
    tooltipEl = document.createElement("div");
    tooltipEl.className = "chartjs-html-tooltip";
    tooltipEl.innerHTML = "<div class=\"chartjs-html-tooltip-inner\"></div>";
    host.appendChild(tooltipEl);
  }

  return tooltipEl;
};

const hideTooltip = (tooltipEl) => {
  tooltipEl.style.opacity = "0";
  tooltipEl.style.pointerEvents = "none";
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), Math.max(min, max));

const renderSections = (container, sections) => {
  const fragment = document.createDocumentFragment();
  sections.forEach((section) => {
    const row = document.createElement("div");
    row.className = "chartjs-tooltip-row";

    const label = document.createElement("span");
    label.className = "chartjs-tooltip-label";
    label.textContent = section.label;
    if (section.color) {
      label.style.setProperty("--tooltip-accent", section.color);
    }

    const value = document.createElement("span");
    value.className = "chartjs-tooltip-value";
    value.textContent = section.value;

    row.appendChild(label);
    row.appendChild(value);
    fragment.appendChild(row);
  });
  container.appendChild(fragment);
};

/**
 * @typedef {{label: string, value: string, color?: string}} TooltipSection
 */

export const createExternalTooltip = ({ renderTooltip }) => ({
  enabled: false,
  position: "nearest",
  external(context) {
    const { chart, tooltip } = context;
    const tooltipEl = getOrCreateTooltipEl(chart);

    if (!tooltip || tooltip.opacity === 0) {
      hideTooltip(tooltipEl);
      return;
    }

    const tooltipModel = renderTooltip({
      chart,
      tooltip,
      points: tooltip.dataPoints || [],
    });

    const inner = tooltipEl.querySelector(".chartjs-html-tooltip-inner");
    inner.innerHTML = "";

    if (tooltipModel?.title) {
      const title = document.createElement("div");
      title.className = "chartjs-tooltip-title";
      title.textContent = tooltipModel.title;
      inner.appendChild(title);
    }

    if (tooltipModel?.sections?.length) {
      renderSections(inner, tooltipModel.sections);
    }

    const host = chart.canvas.parentNode;
    const hostRect = host?.getBoundingClientRect?.();
    const canvasRect = chart.canvas.getBoundingClientRect();
    tooltipEl.style.opacity = "1";
    tooltipEl.style.pointerEvents = "none";
    tooltipEl.style.left = "0px";
    tooltipEl.style.top = "0px";

    const margin = 8;
    const tooltipWidth = tooltipEl.offsetWidth;
    const tooltipHeight = tooltipEl.offsetHeight;
    const hostWidth = hostRect?.width || host?.clientWidth || chart.width || tooltipWidth;
    const hostHeight = hostRect?.height || host?.clientHeight || chart.height || tooltipHeight;
    const caretLeft = canvasRect.left - (hostRect?.left || 0) + tooltip.caretX;
    const caretTop = canvasRect.top - (hostRect?.top || 0) + tooltip.caretY;
    const prefersRight = caretLeft + 16 + tooltipWidth <= hostWidth - margin;
    const left = prefersRight
      ? clamp(caretLeft + 16, margin, hostWidth - tooltipWidth - margin)
      : clamp(caretLeft - tooltipWidth - 16, margin, hostWidth - tooltipWidth - margin);
    const top = clamp(caretTop - tooltipHeight / 2, margin, hostHeight - tooltipHeight - margin);

    tooltipEl.style.left = `${left}px`;
    tooltipEl.style.top = `${top}px`;
  },
});
