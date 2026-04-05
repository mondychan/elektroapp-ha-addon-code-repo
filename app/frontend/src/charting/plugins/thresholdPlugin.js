export const buildThresholdAnnotations = ({ minThreshold, maxThreshold }) => {
  const annotations = {};

  if (minThreshold != null) {
    annotations.minThresholdLine = {
      type: "line",
      yMin: minThreshold,
      yMax: minThreshold,
      borderColor: "rgba(34, 197, 94, 0.4)",
      borderWidth: 2,
      borderDash: [6, 6],
      label: {
        display: true,
        content: "Levná",
        position: "start",
        backgroundColor: "rgba(34, 197, 94, 0.8)",
        color: "#fff",
        font: { size: 10, weight: "bold" },
        padding: 4,
        borderRadius: 4,
      },
    };
  }

  if (maxThreshold != null) {
    annotations.maxThresholdLine = {
      type: "line",
      yMin: maxThreshold,
      yMax: maxThreshold,
      borderColor: "rgba(239, 68, 68, 0.4)",
      borderWidth: 2,
      borderDash: [6, 6],
      label: {
        display: true,
        content: "Drahá",
        position: "end",
        backgroundColor: "rgba(239, 68, 68, 0.8)",
        color: "#fff",
        font: { size: 10, weight: "bold" },
        padding: 4,
        borderRadius: 4,
      },
    };
  }

  return annotations;
};
