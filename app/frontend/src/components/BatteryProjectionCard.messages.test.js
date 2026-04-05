import React from "react";
import { render, screen } from "@testing-library/react";
import BatteryProjectionCard from "./BatteryProjectionCard";

jest.mock("../charting/components/ForecastLineChart", () => () => <div data-testid="soc-chart" />);
jest.mock("../charting/components/BarTimeChart", () => () => <div data-testid="power-chart" />);

describe("BatteryProjectionCard messages", () => {
  test("prefers charging ETA and also shows later reserve ETA", () => {
    render(
      <BatteryProjectionCard
        batteryLoading={false}
        batteryError={null}
        onRefresh={() => {}}
        batteryData={{
          is_today: true,
          enabled: true,
          configured: true,
          date: "2026-04-05",
          status: {
            soc_percent: 56,
            battery_power_w: 1800,
            battery_state: "charging",
            reserve_soc_percent: 10,
            stored_kwh: 5.6,
            available_to_reserve_kwh: 4.6,
            remaining_to_full_kwh: 4.4,
          },
          current_energy: {},
          forecast_solar: {},
          history: { points: [] },
          projection: {
            method: "hybrid_forecast_load_profile",
            confidence: "medium",
            state: "charging",
            eta_to_full_at: "2026-04-05T13:20:00+02:00",
            eta_to_full_minutes: 90,
            eta_to_reserve_after_full_at: "2026-04-05T23:10:00+02:00",
            eta_to_reserve_after_full_minutes: 680,
            points: [],
          },
        }}
      />
    );

    expect(screen.getByText(/Baterie bude nabita cca v 13:20/)).toBeInTheDocument();
    expect(screen.getByText(/Pri aktualnim forecastu klesne k rezerve cca v 23:10/)).toBeInTheDocument();
  });
});
