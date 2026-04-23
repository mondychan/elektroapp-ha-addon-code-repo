import { render, screen, waitFor, cleanup } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import App from "./App";
import { elektroappApi } from "./api/elektroappApi";

vi.mock("./components/PriceChartCard", () => ({ default: () => null }));
vi.mock("./api/elektroappApi", () => ({
  elektroappApi: {
    getPrices: vi.fn(),
    refreshPrices: vi.fn(),
    getConfig: vi.fn(),
    saveConfig: vi.fn(),
    getVersion: vi.fn(),
    getCacheStatus: vi.fn(),
    getCosts: vi.fn(),
    getExport: vi.fn(),
    getBattery: vi.fn(),
    getDailySummary: vi.fn(),
    getBillingMonth: vi.fn(),
    getBillingYear: vi.fn(),
    getEnergyBalance: vi.fn(),
    getHistoryHeatmap: vi.fn(),
    getFeesHistory: vi.fn(),
    saveFeesHistory: vi.fn(),
    getSchedule: vi.fn(),
    getDashboardSnapshot: vi.fn(),
    getSolarForecast: vi.fn(),
    getPndStatus: vi.fn(),
    getPndCacheStatus: vi.fn(),
    verifyPnd: vi.fn(),
    backfillPnd: vi.fn(),
    getPndData: vi.fn(),
    purgePndCache: vi.fn(),
    getHpData: vi.fn(),
    resolveHpEntity: vi.fn(),
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
    vi.resetAllMocks();
    localStorage.clear();
    vi.spyOn(console, "error").mockImplementation(() => {});

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
    elektroappApi.purgePndCache.mockResolvedValue({ purged_files: 0 });
    elektroappApi.getHpData.mockResolvedValue({
      date: "2026-01-01",
      config: { enabled: false, entities: [] },
      kpis: [],
      status_cards: [],
      charts: [],
    });
    elektroappApi.resolveHpEntity.mockResolvedValue({
      entity_id: "sensor.test",
      label: "Test",
      display_kind: "numeric",
      source_kind: "instant",
      kpi_mode: "last",
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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

  test("loads initial overview data from dashboard snapshot without duplicate prices calls", async () => {
    render(<App />);

    await waitFor(() => {
      expect(elektroappApi.getDashboardSnapshot).toHaveBeenCalled();
    });

    expect(elektroappApi.getPrices).not.toHaveBeenCalled();
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

  test("renders HP page and loads its data", async () => {
    render(<App />);

    await userEvent.click(screen.getByRole("tab", { name: "HP" }));

    await waitFor(() => {
      expect(elektroappApi.getHpData).toHaveBeenCalled();
    });

    expect(screen.getByText("HP konfigurace")).toBeInTheDocument();
  });
});
