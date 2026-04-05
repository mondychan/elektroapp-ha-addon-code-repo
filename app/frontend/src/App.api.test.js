import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { elektroappApi } from "./api/elektroappApi";

jest.mock("./components/PriceChartCard", () => () => null);
jest.mock("./api/elektroappApi", () => ({
  elektroappApi: {
    getPrices: jest.fn(),
    refreshPrices: jest.fn(),
    getConfig: jest.fn(),
    saveConfig: jest.fn(),
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
    getDashboardSnapshot: jest.fn(),
    getSolarForecast: jest.fn(),
    getPndStatus: jest.fn(),
    getPndCacheStatus: jest.fn(),
    verifyPnd: jest.fn(),
    backfillPnd: jest.fn(),
    getPndData: jest.fn(),
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
    elektroappApi.saveConfig.mockResolvedValue({ status: "ok" });
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
    elektroappApi.getDashboardSnapshot.mockResolvedValue({
      prices: { prices: [] },
      costs: { points: [], summary: null },
      export: { points: [], summary: null },
      battery: { enabled: false },
      alerts: [],
      comparison: null,
      solar: null,
      version: "test"
    });
    elektroappApi.getSolarForecast.mockResolvedValue(null);
    elektroappApi.getPndStatus.mockResolvedValue({ enabled: false, configured: false, healthy: false, days_count: 0 });
    elektroappApi.getPndCacheStatus.mockResolvedValue({});
    elektroappApi.verifyPnd.mockResolvedValue({ ok: true, message: "verify ok" });
    elektroappApi.backfillPnd.mockResolvedValue({ accepted: true, estimated_days: 1 });
    elektroappApi.getPndData.mockResolvedValue({ days: [] });
  });

  afterEach(() => {
    cleanup();
    jest.clearAllMocks();
    if (console.error.mockRestore) {
      console.error.mockRestore();
    }
  });

  test("shows auth-related InfluxDB error when costs API returns 401", async () => {
    elektroappApi.getDashboardSnapshot.mockRejectedValue({ response: { status: 401 } });
    render(<App />);

    await waitFor(async () => {
      const elements = await screen.findAllByText(/HTTP_401/);
      expect(elements.length).toBeGreaterThan(0);
    });
  });

  test("loads energy balance on overview because the card is visible there", async () => {
    render(<App />);

    await waitFor(() => {
      expect(elektroappApi.getEnergyBalance).toHaveBeenCalled();
    });
  });

  test("loads overview prices separately so tomorrow card can use published next-day data", async () => {
    render(<App />);

    await waitFor(() => {
      expect(elektroappApi.getPrices).toHaveBeenCalledWith();
    });

    await waitFor(() => {
      expect(elektroappApi.getPrices).toHaveBeenCalledWith(expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
    });
  });

  test("planner preset button immediately loads matching duration", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("button", { name: "Zobrazit plánovač" }));

    await waitFor(() => {
      expect(elektroappApi.getSchedule).toHaveBeenCalledWith(120, 3);
    });

    await waitFor(() => {
      expect(screen.getByText(/Vybrano:.*120 min/i)).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "60" }));

    await waitFor(() => {
      expect(elektroappApi.getSchedule).toHaveBeenCalledWith(60, 3);
    });

    await waitFor(() => {
      expect(screen.getByText(/Vybrano:.*60 min/i)).toBeInTheDocument();
    });
  });

  test("renders PND page and loads its status", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("tab", { name: "PND" }));

    await waitFor(() => {
      expect(elektroappApi.getPndStatus).toHaveBeenCalled();
    });

    await userEvent.click(screen.getByRole("button", { name: "Konfigurace" }));
    expect(screen.getByText("PND konfigurace")).toBeInTheDocument();
  });
});
