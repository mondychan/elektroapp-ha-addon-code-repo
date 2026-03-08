/**
 * @typedef {{startSlot: number, endSlot: number, tone?: string, label?: string}} TimeBand
 */

const toneToColor = (tone) => {
  if (tone === "vt") {
    return "rgba(255, 122, 89, 0.08)";
  }
  if (tone === "nt") {
    return "rgba(77, 121, 255, 0.05)";
  }
  return "rgba(255, 255, 255, 0.04)";
};

export const buildTimeBandAnnotations = (bands = []) =>
  bands.reduce((acc, band, index) => {
    if (!Number.isFinite(band?.startSlot) || !Number.isFinite(band?.endSlot)) {
      return acc;
    }

    acc[`timeBand-${index}`] = {
      type: "box",
      xMin: band.startSlot,
      xMax: band.endSlot,
      backgroundColor: toneToColor(band.tone),
      borderWidth: 0,
      label: band.label
        ? {
            display: true,
            content: band.label,
            position: "start",
            color: "rgba(255,255,255,0.92)",
            backgroundColor: "rgba(17, 24, 39, 0.72)",
            padding: 4,
            yAdjust: 8,
          }
        : undefined,
    };

    return acc;
  }, {});

