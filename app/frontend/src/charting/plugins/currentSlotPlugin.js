export const buildCurrentSlotAnnotations = ({ slot, color = "rgba(77, 121, 255, 0.92)" } = {}) => {
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
    },
  };
};
