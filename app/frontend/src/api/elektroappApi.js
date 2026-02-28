import axios from "axios";

const API_PREFIX = "./api";

const get = (path, params) => axios.get(`${API_PREFIX}${path}`, params ? { params } : undefined).then((res) => res.data);
const post = (path, payload) => axios.post(`${API_PREFIX}${path}`, payload).then((res) => res.data);
const put = (path, payload) => axios.put(`${API_PREFIX}${path}`, payload).then((res) => res.data);

export const elektroappApi = {
  getPrices: (date) => get("/prices", date ? { date } : undefined),
  refreshPrices: (payload = {}) => post("/prices/refresh", payload),
  getConfig: () => get("/config"),
  getVersion: () => get("/version"),
  getCacheStatus: () => get("/cache-status"),
  getCosts: (date) => get("/costs", { date }),
  getExport: (date) => get("/export", { date }),
  getBattery: (date) => get("/battery", date ? { date } : undefined),
  getDailySummary: (month) => get("/daily-summary", { month }),
  getBillingMonth: (month) => get("/billing-month", { month }),
  getBillingYear: (year) => get("/billing-year", { year: Number(year) }),
  getEnergyBalance: (period, anchor) => get("/energy-balance", { period, anchor }),
  getHistoryHeatmap: (month, metric) => get("/history-heatmap", { month, metric }),
  getFeesHistory: () => get("/fees-history"),
  saveFeesHistory: (history) => put("/fees-history", { history }),
  getSchedule: (duration, count = 3) => get("/schedule", { duration, count }),
};

export const extractApiError = (err) => {
  const status = err?.response?.status ?? null;
  const data = err?.response?.data;
  const wrapped = data?.error;
  if (wrapped && typeof wrapped === "object") {
    const code = wrapped.code ? String(wrapped.code) : status ? `HTTP_${status}` : "UNKNOWN_ERROR";
    const message =
      wrapped.message != null ? String(wrapped.message) : wrapped.detail != null ? String(wrapped.detail) : "Request failed.";
    return {
      status,
      code,
      message,
      detail: wrapped.detail ?? null,
      requestId: wrapped.request_id ?? null,
    };
  }

  const detail = data?.detail;
  if (detail != null) {
    return {
      status,
      code: status ? `HTTP_${status}` : "UNKNOWN_ERROR",
      message: String(detail),
      detail,
      requestId: null,
    };
  }

  if (status) {
    return {
      status,
      code: `HTTP_${status}`,
      message: `HTTP ${status}`,
      detail: null,
      requestId: null,
    };
  }

  return {
    status: null,
    code: "NETWORK_ERROR",
    message: "Network error",
    detail: null,
    requestId: null,
  };
};

export const formatApiError = (err, fallbackMessage = "Request failed.") => {
  const parsed = extractApiError(err);
  const message = parsed.message && parsed.message !== "Network error" ? parsed.message : fallbackMessage;
  return parsed.code ? `${message} [${parsed.code}]` : message;
};

export const buildInfluxError = (err) => {
  const parsed = extractApiError(err);
  if (parsed.status === 401) {
    return `Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo. [${parsed.code}]`;
  }
  if (parsed.detail) {
    return parsed.code ? `${String(parsed.detail)} [${parsed.code}]` : String(parsed.detail);
  }
  if (parsed.status) {
    return `Chyba pri nacitani z InfluxDB (HTTP ${parsed.status}). [${parsed.code}]`;
  }
  return `Nepodarilo se pripojit k InfluxDB. [${parsed.code}]`;
};
