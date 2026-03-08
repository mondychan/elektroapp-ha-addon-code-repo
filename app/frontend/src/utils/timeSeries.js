import { formatSlotToTime } from "./formatters";

export const parseIsoLocalTimeParts = (iso) => {
  if (!iso || typeof iso !== "string") {
    return null;
  }
  const match = iso.match(/T(\d{2}):(\d{2})/);
  if (!match) {
    return null;
  }
  const hour = Number.parseInt(match[1], 10);
  const minute = Number.parseInt(match[2], 10);
  if (!Number.isFinite(hour) || !Number.isFinite(minute)) {
    return null;
  }
  return { hour, minute };
};

export const getQuarterHourSlotFromIso = (iso) => {
  const parts = parseIsoLocalTimeParts(iso);
  if (!parts) return null;
  const slot = parts.hour * 4 + Math.floor(parts.minute / 15);
  return slot >= 0 && slot < 96 ? slot : null;
};

export const buildQuarterHourSeries = (points, mapValues, defaultValues = {}) => {
  const rows = Array.from({ length: 96 }, (_, slot) => ({
    slot,
    time: formatSlotToTime(slot),
    ...defaultValues,
  }));

  (points || []).forEach((point) => {
    const slot = getQuarterHourSlotFromIso(point?.time);
    if (!Number.isInteger(slot)) return;
    rows[slot] = {
      ...rows[slot],
      ...mapValues(point, slot),
    };
  });

  return rows;
};
