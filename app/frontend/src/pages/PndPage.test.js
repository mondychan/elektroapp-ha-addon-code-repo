import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PndPage from "./PndPage";
import { elektroappApi } from "../api/elektroappApi";

jest.mock("../api/elektroappApi", () => ({
  elektroappApi: {
    getPndStatus: jest.fn(),
    saveConfig: jest.fn(),
    verifyPnd: jest.fn(),
    backfillPnd: jest.fn(),
    getPndData: jest.fn(),
  },
  formatApiError: (err, fallbackMessage = "Request failed.") => fallbackMessage,
}));

describe("PndPage", () => {
  beforeEach(() => {
    jest.resetAllMocks();
    elektroappApi.getPndStatus.mockResolvedValue({
      enabled: true,
      configured: true,
      healthy: true,
      state: "cache_ready",
      state_message: "PND cache je pripravena.",
      cached_from: "2026-04-01",
      cached_to: "2026-04-04",
      days_count: 4,
    });
    elektroappApi.saveConfig.mockResolvedValue({ status: "ok", pnd_verify: { message: "verify after save" } });
    elektroappApi.verifyPnd.mockResolvedValue({ ok: true, message: "verify ok" });
    elektroappApi.backfillPnd.mockResolvedValue({ accepted: true, estimated_days: 7 });
    elektroappApi.getPndData.mockResolvedValue({ days: [] });
  });

  test("saves config and triggers verify/backfill actions", async () => {
    const refreshConfig = jest.fn().mockResolvedValue({});
    render(
      <PndPage
        config={{
          pnd: {
            enabled: true,
            username: "user@example.com",
            password: "secret",
            meter_id: "3000012345",
            verify_on_startup: true,
            nightly_sync_enabled: true,
            nightly_sync_window_start_hour: 2,
            nightly_sync_window_end_hour: 7,
          },
        }}
        refreshConfig={refreshConfig}
      />
    );

    await waitFor(() => {
      expect(elektroappApi.getPndStatus).toHaveBeenCalled();
    });

    // Reveal config form
    await userEvent.click(screen.getByRole("button", { name: "Konfigurace" }));

    await userEvent.click(screen.getByRole("button", { name: "Ulozit PND konfiguraci" }));
    await waitFor(() => {
      expect(elektroappApi.saveConfig).toHaveBeenCalled();
    });

    // Reveal status section
    await userEvent.click(screen.getByRole("button", { name: "Stav" }));

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "Spustit verify" })).toBeInTheDocument();
    });

    await userEvent.click(screen.getByRole("button", { name: "Spustit verify" }));
    await waitFor(() => {
      expect(elektroappApi.verifyPnd).toHaveBeenCalled();
    });

    await waitFor(() => {
      expect(screen.getByRole("button", { name: "7 dni" })).toBeEnabled();
    });

    await userEvent.click(screen.getByRole("button", { name: "7 dni" }));
    await waitFor(() => {
      expect(elektroappApi.backfillPnd).toHaveBeenCalledWith("week");
    });

    expect(screen.getByText(/02:00 a 07:59/)).toBeInTheDocument();
  });

  test("renders explicit portal changed diagnostics", async () => {
    elektroappApi.getPndStatus.mockResolvedValueOnce({
      enabled: true,
      configured: true,
      healthy: false,
      state: "portal_changed",
      state_message: "Portal PND zmenil datovou strukturu.",
      last_error: {
        code: "PND_PORTAL_CHANGED",
        message: "PND payload neobsahuje pole 'series' v ocekavanem formatu.",
        details: {
          missing_html_marker: "Namerena data",
          payload_keys: ["result", "status"],
        },
      },
      days_count: 0,
    });

    render(
      <PndPage
        config={{
          pnd: {
            enabled: true,
            username: "user@example.com",
            password: "secret",
            meter_id: "3000012345",
            verify_on_startup: true,
            nightly_sync_enabled: true,
            nightly_sync_window_start_hour: 2,
            nightly_sync_window_end_hour: 7,
          },
        }}
        refreshConfig={jest.fn().mockResolvedValue({})}
      />
    );

    expect(await screen.findByText("PND zmenilo strukturu nebo endpoint contract")).toBeInTheDocument();
    
    // Reveal diagnostics
    await userEvent.click(screen.getByRole("button", { name: "Stav" }));
    
    expect(screen.getByText(/Chybi HTML marker: Namerena data/)).toBeInTheDocument();
    expect(screen.getByText(/Payload keys: result, status/)).toBeInTheDocument();
  });
});
