/**
 * @typedef {{slot: number, kind: "start" | "stop", label?: string}} TransitionMarker
 */

export const buildTransitionAnnotations = (markers = []) =>
  markers.reduce((acc, marker, index) => {
    if (!Number.isInteger(marker?.slot)) {
      return acc;
    }

    const color = marker.kind === "start" ? "rgba(57, 181, 106, 0.34)" : "rgba(212, 106, 106, 0.3)";
    acc[`transition-${index}`] = {
      type: "line",
      xMin: marker.slot,
      xMax: marker.slot,
      borderColor: color,
      borderWidth: 1.5,
      borderDash: [3, 4],
    };
    return acc;
  }, {});
