export const formatDate = (date) => date.toLocaleDateString("cs-CZ");

export const formatMonthLabel = (monthStr) => {
  if (!monthStr) return "-";
  const [year, month] = monthStr.split("-");
  if (!year || !month) return monthStr;
  const date = new Date(`${year}-${month}-01T00:00:00`);
  return date.toLocaleDateString("cs-CZ", { year: "numeric", month: "long" });
};

export const toDateInputValue = (date) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

export const formatBytes = (bytes) => {
  if (bytes == null) return "-";
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  const mb = kb / 1024;
  if (mb < 1024) return `${mb.toFixed(1)} MB`;
  const gb = mb / 1024;
  return `${gb.toFixed(1)} GB`;
};

export const formatCurrency = (value) => {
  if (value == null || Number.isNaN(value)) return "-";
  return `${value.toFixed(2)},-Kc`;
};

export const formatSlotToTime = (slot) => {
  const hour = Math.floor(slot / 4);
  const minute = (slot % 4) * 15;
  return `${hour.toString().padStart(2, "0")}:${minute.toString().padStart(2, "0")}`;
};
