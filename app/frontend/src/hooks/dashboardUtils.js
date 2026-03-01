export const getTodayDateStr = () => {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

export const normalizeEnergyBalanceAnchor = (period, currentAnchor) => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  if (period === "year") {
    const parsed = Number.parseInt(currentAnchor, 10);
    return Number.isFinite(parsed) ? String(parsed) : String(y);
  }
  if (period === "month") {
    if (/^\d{4}-\d{2}$/.test(currentAnchor || "")) return currentAnchor;
    return `${y}-${m}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(currentAnchor || "")) return currentAnchor;
  return `${y}-${m}-${d}`;
};

export const shiftEnergyBalanceAnchor = (period, anchorValue, delta) => {
  const anchorNorm = normalizeEnergyBalanceAnchor(period, anchorValue);
  if (period === "year") {
    return String((Number.parseInt(anchorNorm, 10) || new Date().getFullYear()) + delta);
  }
  if (period === "month") {
    const [year, month] = anchorNorm.split("-").map(Number);
    const dt = new Date(year, (month || 1) - 1 + delta, 1);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
  }
  const [year, month, day] = anchorNorm.split("-").map(Number);
  const dt = new Date(year, (month || 1) - 1, day || 1);
  dt.setDate(dt.getDate() + delta * 7);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
};
