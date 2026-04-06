import { render, screen } from "@testing-library/react";
import SolarForecastCard from "./SolarForecastCard";

describe("SolarForecastCard", () => {
  test("renders raw and adjusted today and tomorrow values", () => {
    render(
      <SolarForecastCard
        solarForecast={{
          enabled: true,
          status: {
            production_today: 35.84,
            production_today_remaining: 10.0,
            production_tomorrow: 59.77,
            energy_current_hour: 1.1,
            energy_next_hour: 2.2,
            power_production_next_hour_w: 1800,
            power_production_next_12hours_w: 1500,
            power_production_next_24hours_w: 300,
          },
          actual: {
            production_today_kwh: 40.12,
            power_now_w: 1200,
          },
          comparison: {
            model_version: "v2_hourly_bias",
            adjusted_projection_today_kwh: 44.5,
            adjusted_projection_tomorrow_kwh: 57.2,
            adjusted_current_hour_kwh: 1.0,
            adjusted_next_hour_kwh: 2.0,
            future_profile_source: "live_anchors_plus_historical_shape",
          },
          history: {
            days_tracked: 120,
            cache_days: 200,
            hourly_slots_tracked: 1500,
            profile_sources_available: {
              historical_hourly: true,
              live_next_hour: true,
              live_next_12hours: true,
              live_next_24hours: true,
            },
            recent_days: [],
          },
        }}
      />
    );

    expect(screen.getByText("Forecast dnes")).toBeInTheDocument();
    expect(screen.getByText("Systémový odhad dnes")).toBeInTheDocument();
    expect(screen.getByText("Forecast zítra")).toBeInTheDocument();
    expect(screen.getByText("Systémový odhad zítra")).toBeInTheDocument();
  });
});
