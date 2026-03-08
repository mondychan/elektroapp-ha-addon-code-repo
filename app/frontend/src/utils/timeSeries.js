import { formatSlotToTime } from "./formatters";

export const getQuarterHourSlotFromIso = (iso) => {
  if (!iso) return null;
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return null;
  const slot = dt.getHours() * 4 + Math.floor(dt.getMinutes() / 15);
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
