import { render, screen } from "@testing-library/react";
import App from "./App";
import { elektroappApi } from "./api/elektroappApi";

jest.mock("./components/PriceChartCard", () => () => null);
jest.mock("./api/elektroappApi", () => ({
  elektroappApi: {
    getPrices: jest.fn(),
    refreshPrices: jest.fn(),
    getConfig: jest.fn(),
    getVersion: jest.fn(),
    getCacheStatus: jest.fn(),
    getCosts: jest.fn(),
    getExport: jest.fn(),
    getBattery: jest.fn(),
    getDailySummary: jest.fn(),
    getBillingMonth: jest.fn(),
    getBillingYear: jest.fn(),
    getEnergyBalance: jest.fn(),
    getHistoryHeatmap: jest.fn(),
    getFeesHistory: jest.fn(),
    saveFeesHistory: jest.fn(),
    getSchedule: jest.fn(),
  },
  extractApiError: (err) => {
    const status = err?.response?.status ?? null;
    const detail = err?.response?.data?.detail;
    return {
      status,
      code: status ? `HTTP_${status}` : "NETWORK_ERROR",
      message: detail ? String(detail) : status ? `HTTP ${status}` : "Network error",
    };
  },
  formatApiError: (err, fallbackMessage = "Request failed.") => {
    const status = err?.response?.status ?? null;
    const detail = err?.response?.data?.detail;
    const code = status ? `HTTP_${status}` : "NETWORK_ERROR";
    const message = detail ? String(detail) : fallbackMessage;
    return `${message} [${code}]`;
  },
  buildInfluxError: (err) => {
    if (err?.response?.status === 401) {
      return "Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo. [HTTP_401]";
    }
    if (err?.response?.status) {
      return `Chyba pri nacitani z InfluxDB (HTTP ${err.response.status}). [HTTP_${err.response.status}]`;
    }
    return "Nepodarilo se pripojit k InfluxDB. [NETWORK_ERROR]";
  },
}));

describe("App API states", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    localStorage.clear();
    jest.spyOn(console, "error").mockImplementation(() => {});

    elektroappApi.getPrices.mockResolvedValue({ prices: [] });
    elektroappApi.getConfig.mockResolvedValue({
      price_provider: "spotovaelektrina",
      tarif: { vt_periods: [] },
    });
    elektroappApi.getVersion.mockResolvedValue({ version: "test" });
    elektroappApi.getCosts.mockRejectedValue({ response: { status: 401 } });
    elektroappApi.getExport.mockResolvedValue({ points: [], summary: null });
    elektroappApi.getBattery.mockResolvedValue({ enabled: false });
    elektroappApi.getDailySummary.mockResolvedValue({ days: [], summary: null });
    elektroappApi.getBillingMonth.mockResolvedValue({});
    elektroappApi.getBillingYear.mockResolvedValue({});
    elektroappApi.getCacheStatus.mockResolvedValue({});
    elektroappApi.getFeesHistory.mockResolvedValue({ history: [] });
    elektroappApi.saveFeesHistory.mockResolvedValue({ history: [] });
    elektroappApi.refreshPrices.mockResolvedValue({ refreshed: [] });
    elektroappApi.getEnergyBalance.mockResolvedValue({});
    elektroappApi.getHistoryHeatmap.mockResolvedValue({});
    elektroappApi.getSchedule.mockResolvedValue({ recommendations: [], note: null });
  });

  afterEach(() => {
    if (console.error.mockRestore) {
      console.error.mockRestore();
    }
  });

  test("shows auth-related InfluxDB error when costs API returns 401", async () => {
    render(<App />);

    expect(
      await screen.findByText("Nepodarilo se overit pristup k InfluxDB (401). Zkontroluj uzivatele a heslo. [HTTP_401]")
    ).toBeInTheDocument();
  });
});
