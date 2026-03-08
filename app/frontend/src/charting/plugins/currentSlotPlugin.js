export const buildCurrentSlotAnnotations = ({ slot, label, color = "rgba(77, 121, 255, 0.92)" } = {}) => {
  if (!Number.isInteger(slot)) {
    return {};
  }

  return {
    currentSlotLine: {
      type: "line",
      xMin: slot,
      xMax: slot,
      borderColor: color,
      borderWidth: 2,
      borderDash: [4, 4],
      label: label
        ? {
            display: true,
            content: label,
            position: "start",
            backgroundColor: color,
            color: "#ffffff",
            padding: 6,
            yAdjust: -6,
          }
        : undefined,
    },
  };
};

