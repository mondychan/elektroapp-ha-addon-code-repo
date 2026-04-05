export const getTodayDateStr = () => {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

export const getCurrentMonthStr = () => getTodayDateStr().slice(0, 7);

export const getCurrentYearStr = () => String(new Date().getFullYear());

const clampNumber = (value, minValue, maxValue) => {
  const parsed = Number.parseInt(String(value), 10);
  if (!Number.isFinite(parsed)) return String(maxValue);
  return String(Math.min(Math.max(parsed, minValue), maxValue));
};

export const clampDateValue = (value, maxDate = getTodayDateStr()) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || "")) return maxDate;
  return value > maxDate ? maxDate : value;
};

export const clampMonthValue = (value, maxMonth = getCurrentMonthStr()) => {
  if (!/^\d{4}-\d{2}$/.test(value || "")) return maxMonth;
  return value > maxMonth ? maxMonth : value;
};

export const clampYearValue = (value, maxYear = getCurrentYearStr()) => (
  clampNumber(value, 1900, Number.parseInt(maxYear, 10) || new Date().getFullYear())
);

export const normalizeEnergyBalanceAnchor = (period, currentAnchor) => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  if (period === "year") {
    return clampYearValue(currentAnchor, String(y));
  }
  if (period === "month") {
    return clampMonthValue(currentAnchor, `${y}-${m}`);
  }
  return clampDateValue(currentAnchor, `${y}-${m}-${d}`);
};

export const getMaxEnergyBalanceAnchor = (period) => {
  if (period === "year") return getCurrentYearStr();
  if (period === "month") return getCurrentMonthStr();
  return getTodayDateStr();
};

export const shiftEnergyBalanceAnchor = (period, anchorValue, delta) => {
  const anchorNorm = normalizeEnergyBalanceAnchor(period, anchorValue);
  if (period === "year") {
    return clampYearValue(
      String((Number.parseInt(anchorNorm, 10) || new Date().getFullYear()) + delta),
      getCurrentYearStr()
    );
  }
  if (period === "month") {
    const [year, month] = anchorNorm.split("-").map(Number);
    const dt = new Date(year, (month || 1) - 1 + delta, 1);
    return clampMonthValue(
      `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`,
      getCurrentMonthStr()
    );
  }
  const [year, month, day] = anchorNorm.split("-").map(Number);
  const dt = new Date(year, (month || 1) - 1, day || 1);
  dt.setDate(dt.getDate() + delta * 7);
  return clampDateValue(
    `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`,
    getTodayDateStr()
  );
};
