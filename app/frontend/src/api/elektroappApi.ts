import axios from "axios";

const API_PREFIX = "./api";

const get = (path: string, params?: any) => axios.get(`${API_PREFIX}${path}`, params ? { params } : undefined).then((res) => res.data);
const post = (path: string, payload?: any) => axios.post(`${API_PREFIX}${path}`, payload).then((res) => res.data);
const put = (path: string, payload?: any) => axios.put(`${API_PREFIX}${path}`, payload).then((res) => res.data);

export const elektroappApi = {
  getPrices: (date?: string) => get("/prices", date ? { date } : undefined),
  refreshPrices: (payload = {}) => post("/prices/refresh", payload),
  getConfig: () => get("/config"),
  saveConfig: (config: any) => post("/config", config),
  getVersion: () => get("/version"),
  getCacheStatus: () => get("/cache-status"),
  getCosts: (date: string) => get("/costs", { date }),
  getExport: (date: string) => get("/export", { date }),
  getBattery: (date?: string) => get("/battery", date ? { date } : undefined),
  getDailySummary: (month: string) => get("/daily-summary", { month }),
  getBillingMonth: (month: string) => get("/billing-month", { month }),
  getBillingYear: (year: number | string) => get("/billing-year", { year: Number(year) }),
  getEnergyBalance: (period: string, anchor: string) => get("/energy-balance", { period, anchor }),
  getHistoryHeatmap: (month: string, metric: string) => get("/history-heatmap", { month, metric }),
  getFeesHistory: () => get("/fees-history"),
  saveFeesHistory: (history: any) => put("/fees-history", { history }),
  getSchedule: (duration: number, count = 3) => get("/schedule", { duration, count }),
  getAlerts: () => get("/alerts"),
  getComparison: (date?: string) => get("/comparison", date ? { date } : undefined),
  getSolarForecast: () => get("/solar-forecast"),
  getDashboardSnapshot: (date?: string) => get("/dashboard-snapshot", date ? { date } : undefined),
  getExportCsv: (month: string) => get("/export-csv", { month }),
  getPndStatus: () => get("/pnd/status"),
  getPndCacheStatus: () => get("/pnd/cache-status"),
  verifyPnd: () => post("/pnd/verify"),
  backfillPnd: (range: string) => post("/pnd/backfill", { range }),
  getPndData: (from: string, to: string) => get("/pnd/data", { from, to }),
  purgePndCache: () => post("/pnd/purge-cache"),
  getHpData: (date?: string) => get("/hp/data", date ? { date } : undefined),
  resolveHpEntity: (entity_id: string) => post("/hp/resolve-entity", { entity_id }),
};

const formatErrorDetail = (detail: any): string | null => {
  if (detail == null) return null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (item && typeof item === "object") {
          const loc = Array.isArray(item.loc) ? item.loc.join(".") : null;
          const msg = item.msg ? String(item.msg) : null;
          if (loc && msg) return `${loc}: ${msg}`;
          if (msg) return msg;
          try {
            return JSON.stringify(item);
          } catch {
            return String(item);
          }
        }
        return String(item);
      })
      .filter(Boolean);
    return parts.length ? parts.join("; ") : null;
  }
  if (typeof detail === "object") {
    if (detail.message) return String(detail.message);
    if (detail.msg) return String(detail.msg);
    try {
      return JSON.stringify(detail);
    } catch {
      return String(detail);
    }
  }
  return String(detail);
};

export const extractApiError = (err: any) => {
  const status = err?.response?.status ?? null;
  const data = err?.response?.data;
  const wrapped = data?.error;
  if (wrapped && typeof wrapped === "object") {
    const code = wrapped.code ? String(wrapped.code) : status ? `HTTP_${status}` : "UNKNOWN_ERROR";
    const detailText = formatErrorDetail(wrapped.detail);
    const message =
      wrapped.message != null ? String(wrapped.message) : detailText != null ? detailText : "Request failed.";
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
    const detailText = formatErrorDetail(detail);
    const detailCode = typeof detail === "object" && detail?.code ? String(detail.code) : null;
    return {
      status,
      code: detailCode ?? (status ? `HTTP_${status}` : "UNKNOWN_ERROR"),
      message: detailText ?? "Request failed.",
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

export const formatApiError = (err: any, fallbackMessage = "Request failed.") => {
  const parsed = extractApiError(err);
  const message = parsed.message && parsed.message !== "Network error" ? parsed.message : fallbackMessage;
  return parsed.code ? `${message} [${parsed.code}]` : message;
};

export const buildInfluxError = (err: any) => {
  const parsed = extractApiError(err);
  if (parsed.status === 401) {
    return `Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo. [${parsed.code}]`;
  }
  if (parsed.detail) {
    return parsed.code ? `${parsed.message} [${parsed.code}]` : parsed.message;
  }
  if (parsed.status) {
    return `Chyba pri nacitani z InfluxDB (HTTP ${parsed.status}). [${parsed.code}]`;
  }
  return `Nepodarilo se pripojit k InfluxDB. [${parsed.code}]`;
};
